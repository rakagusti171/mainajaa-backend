import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
import midtransclient

class Kupon(models.Model):
    kode = models.CharField(max_length=50, unique=True)
    diskon_persen = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Diskon dalam persentase (misal: 10 untuk 10%)"
    )
    aktif = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    digunakan_oleh = models.ManyToManyField(User, related_name='kupon_digunakan', blank=True)

    def __str__(self):
        return f"{self.kode} ({self.diskon_persen}%)"

class AkunGaming(models.Model):
    GAME_CHOICES = [
        ('Mobile Legends', 'Mobile Legends'),
        ('PUBG Mobile', 'PUBG Mobile'),
        ('Black Desert Mobile', 'Black Desert Mobile'),
        ('HAIKYU!!', 'HAIKYU!!'),
        ('Lainnya', 'Lainnya'),
    ]
    game = models.CharField(max_length=50, choices=GAME_CHOICES)
    nama_akun = models.CharField(max_length=100)
    level = models.PositiveIntegerField(default=1)
    deskripsi = models.TextField()
    harga = models.DecimalField(max_digits=10, decimal_places=2)
    gambar = models.ImageField(upload_to='account_images/',blank=True, null=True)
    is_sold = models.BooleanField(default=False)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    favorited_by = models.ManyToManyField(User, related_name='favorite_accounts', blank=True)
    akun_email = models.CharField(max_length=255, blank=True, null=True, help_text="Email/Username akun game (akan dienkripsi)")
    akun_password = models.CharField(max_length=255, blank=True, null=True, help_text="Password akun game (akan dienkripsi)")

    def __str__(self):
        return f"{self.nama_akun} - {self.game}"

class TopUpProduct(models.Model):
    GAME_CHOICES = [
        ('Mobile Legends', 'Mobile Legends'),
        ('PUBG Mobile', 'PUBG Mobile'),
        ('Black Desert Mobile', 'Black Desert Mobile'),
        ('HAIKYU!!', 'HAIKYU!!'),
        ('Lainnya', 'Lainnya'),
    ]
    game = models.CharField(max_length=50, choices=GAME_CHOICES)
    nama_paket = models.CharField(max_length=100)
    harga = models.DecimalField(max_digits=10, decimal_places=2)
    gambar = models.ImageField(upload_to='topup_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.game} - {self.nama_paket}"

class Pembelian(models.Model):
    STATUS_CHOICES = [('PENDING', 'Pending'), ('COMPLETED', 'Completed'), ('CANCELED', 'Canceled')]
    pembeli = models.ForeignKey(User, on_delete=models.CASCADE)
    akun = models.ForeignKey(AkunGaming, on_delete=models.SET_NULL, null=True, blank=True)
    harga_total = models.DecimalField(max_digits=10, decimal_places=2)
    harga_asli = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    kupon = models.ForeignKey(Kupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='pembelian')
    kode_transaksi = models.CharField(max_length=50, default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    midtrans_token = models.CharField(max_length=255, null=True, blank=True)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    ulasan = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if isinstance(self.kode_transaksi, uuid.UUID):
             self.kode_transaksi = f"AKUN-{self.kode_transaksi}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Transaksi {self.kode_transaksi} oleh {self.pembeli.username}"

    @classmethod
    def create_pembelian(cls, pembeli, akun, kode_kupon_str=None):
        harga_asli = akun.harga
        harga_final = harga_asli
        kupon_obj = None

        if kode_kupon_str:
            try:
                kupon = Kupon.objects.get(kode__iexact=kode_kupon_str, aktif=True)
                if kupon.digunakan_oleh.filter(id=pembeli.id).exists():
                    raise ValueError('Kupon ini sudah pernah Anda gunakan.')
                diskon = (harga_asli * Decimal(kupon.diskon_persen / 100))
                harga_final = harga_asli - diskon
                kupon_obj = kupon
            except Kupon.DoesNotExist:
                raise ValueError('Kupon yang Anda kirim tidak valid.')

        pembelian = cls.objects.create(
            pembeli=pembeli,
            akun=akun,
            harga_total=harga_final,
            harga_asli=harga_asli,
            kupon=kupon_obj,
            status='PENDING'
        )

        try:
            snap = midtransclient.Snap(
                is_production=settings.MIDTRANS_IS_PRODUCTION,
                server_key=settings.MIDTRANS_SERVER_KEY,
                client_key=settings.MIDTRANS_CLIENT_KEY
            )
            transaction_details = {
                'order_id': str(pembelian.kode_transaksi),
                'gross_amount': int(pembelian.harga_total)
            }
            transaction = snap.create_transaction({'transaction_details': transaction_details})
            midtrans_token = transaction['token']
            pembelian.midtrans_token = midtrans_token
            pembelian.save()
            return pembelian, midtrans_token
        except Exception as e:
            pembelian.delete()
            raise ValueError(f"Gagal membuat token pembayaran Midtrans: {e}") from e

class TopUpPembelian(models.Model):
    STATUS_CHOICES = [('PENDING', 'Pending'), ('COMPLETED', 'Completed'), ('CANCELED', 'Canceled')]
    produk = models.ForeignKey(TopUpProduct, on_delete=models.SET_NULL, null=True)
    pembeli = models.ForeignKey(User, on_delete=models.CASCADE)
    game_user_id = models.CharField(max_length=100)
    game_zone_id = models.CharField(max_length=50, blank=True, null=True)
    harga_pembelian = models.DecimalField(max_digits=10, decimal_places=2)
    harga_asli = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    kupon = models.ForeignKey(Kupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='topup_pembelian')
    kode_transaksi = models.CharField(max_length=50, default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    midtrans_token = models.CharField(max_length=255, null=True, blank=True)
    tanggal_pembelian = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if isinstance(self.kode_transaksi, uuid.UUID):
            self.kode_transaksi = f"TOPUP-{self.kode_transaksi}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"TopUp {self.produk.nama_paket if self.produk else 'N/A'} oleh {self.pembeli.username} ({self.kode_transaksi})"

    @property
    def dibuat_pada(self):
        return self.tanggal_pbembelian

    @classmethod
    def create_pembelian_topup(cls, pembeli, produk, game_user_id, game_zone_id=None, kode_kupon_str=None):
        harga_asli = produk.harga
        harga_final = harga_asli
        kupon_obj = None

        if kode_kupon_str:
            try:
                kupon = Kupon.objects.get(kode__iexact=kode_kupon_str, aktif=True)
                if kupon.digunakan_oleh.filter(id=pembeli.id).exists():
                    raise ValueError('Kupon ini sudah pernah Anda gunakan.')
                diskon = (harga_asli * Decimal(kupon.diskon_persen / 100))
                harga_final = harga_asli - diskon
                kupon_obj = kupon
            except Kupon.DoesNotExist:
                raise ValueError('Kupon yang Anda kirim tidak valid.')

        pembelian = cls.objects.create(
            pembeli=pembeli,
            produk=produk,
            game_user_id=game_user_id,
            game_zone_id=game_zone_id,
            harga_pembelian=harga_final,
            harga_asli=harga_asli,
            kupon=kupon_obj,
            status='PENDING'
        )

        try:
            snap = midtransclient.Snap(
                is_production=settings.MIDTRANS_IS_PRODUCTION,
                server_key=settings.MIDTRANS_SERVER_KEY,
                client_key=settings.MIDTRANS_CLIENT_KEY
            )
            transaction_details = {
                'order_id': str(pembelian.kode_transaksi),
                'gross_amount': int(pembelian.harga_pembelian)
            }
            transaction = snap.create_transaction({'transaction_details': transaction_details})
            midtrans_token = transaction['token']
            pembelian.midtrans_token = midtrans_token
            pembelian.save()
            return pembelian, midtrans_token
        except Exception as e:
            pembelian.delete()
            print(f"Midtrans transaction creation failed: {e}")
            raise ValueError(f"Gagal membuat token pembayaran Midtrans: {e}") from e

class AkunGamingImage(models.Model):
    akun = models.ForeignKey(AkunGaming, related_name='images', on_delete=models.CASCADE)
    gambar = models.ImageField(upload_to='account_gallery/')

    def __str__(self):
        return f"Gambar untuk {self.akun.nama_akun}"