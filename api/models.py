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
    stock = models.PositiveIntegerField(default=1, help_text="Jumlah stok akun yang tersedia")
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    favorited_by = models.ManyToManyField(User, related_name='favorite_accounts', blank=True)
    akun_email = models.CharField(max_length=255, blank=True, null=True, help_text="Email/Username akun game (akan dienkripsi)")
    akun_password = models.CharField(max_length=255, blank=True, null=True, help_text="Password akun game (akan dienkripsi)")

    @property
    def is_available(self):
        """Check if account is available (has stock and not sold)"""
        return self.stock > 0 and not self.is_sold

    def __str__(self):
        return f"{self.nama_akun} - {self.game} (Stock: {self.stock})"

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
    stock = models.PositiveIntegerField(default=999, help_text="Jumlah stok top-up yang tersedia (999 = unlimited)")

    @property
    def is_available(self):
        """Check if top-up product is available"""
        return self.stock > 0

    def __str__(self):
        return f"{self.game} - {self.nama_paket} (Stock: {self.stock})"

class Pembelian(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('MIDTRANS', 'Midtrans'),
        ('CRYPTO_USDT', 'USDT'),
        ('CRYPTO_ETH', 'Ethereum (ETH)'),
        ('CRYPTO_SOL', 'Solana (SOL)'),
    ]
    STATUS_CHOICES = [('PENDING', 'Pending'), ('COMPLETED', 'Completed'), ('CANCELED', 'Canceled')]
    pembeli = models.ForeignKey(User, on_delete=models.CASCADE)
    akun = models.ForeignKey(AkunGaming, on_delete=models.SET_NULL, null=True, blank=True)
    harga_total = models.DecimalField(max_digits=10, decimal_places=2)
    harga_asli = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    kupon = models.ForeignKey(Kupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='pembelian')
    kode_transaksi = models.CharField(max_length=50, default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='MIDTRANS')
    midtrans_token = models.CharField(max_length=255, null=True, blank=True)
    # Crypto payment fields
    crypto_address = models.CharField(max_length=255, null=True, blank=True, help_text="Wallet address untuk crypto payment")
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, help_text="Jumlah crypto yang harus dibayar")
    crypto_currency = models.CharField(max_length=10, null=True, blank=True, help_text="Currency code (USDT, ETH, SOL)")
    crypto_tx_hash = models.CharField(max_length=255, null=True, blank=True, help_text="Transaction hash setelah pembayaran")
    crypto_confirmed_at = models.DateTimeField(null=True, blank=True, help_text="Waktu konfirmasi pembayaran crypto")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    ulasan = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if isinstance(self.kode_transaksi, uuid.UUID):
             self.kode_transaksi = f"AKUN-{self.kode_transaksi}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Transaksi {self.kode_transaksi} oleh {self.pembeli.username}"

    @classmethod
    def create_pembelian(cls, pembeli, akun, kode_kupon_str=None, payment_method='MIDTRANS'):
        # Check stock availability
        if akun.stock <= 0:
            raise ValueError('Maaf, stok akun ini sudah habis.')
        if akun.is_sold:
            raise ValueError('Akun ini sudah terjual.')

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
            status='PENDING',
            payment_method=payment_method
        )

        # Handle payment based on payment method
        if payment_method == 'MIDTRANS':
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
        else:
            # Crypto payment
            from .crypto_payment import calculate_crypto_amount, get_crypto_wallet_address
            crypto_code = payment_method.replace('CRYPTO_', '')
            crypto_amount, crypto_price, idr_rate = calculate_crypto_amount(pembelian.harga_total, crypto_code)
            wallet_address = get_crypto_wallet_address(crypto_code)
            
            if not crypto_amount or not wallet_address:
                pembelian.delete()
                raise ValueError(f"Gagal membuat pembayaran crypto untuk {crypto_code}")
            
            pembelian.crypto_address = wallet_address
            pembelian.crypto_amount = crypto_amount
            pembelian.crypto_currency = crypto_code
            pembelian.save()
            
            return pembelian, None  # No token for crypto, return payment details instead

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
        return self.tanggal_pembelian

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

class Cart(models.Model):
    """Model untuk shopping cart user"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart untuk {self.user.username}"

    def get_total_price(self):
        """Menghitung total harga semua item di cart"""
        return sum(item.get_total_price() for item in self.items.all())

    def get_item_count(self):
        """Menghitung jumlah item di cart"""
        return self.items.count()

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

class CartItem(models.Model):
    """Model untuk item dalam cart"""
    ITEM_TYPE_CHOICES = [
        ('AKUN', 'Akun Gaming'),
        ('TOPUP', 'Top Up'),
    ]
    
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES)
    
    # Untuk item type AKUN
    akun = models.ForeignKey(AkunGaming, on_delete=models.CASCADE, null=True, blank=True)
    
    # Untuk item type TOPUP
    topup_product = models.ForeignKey(TopUpProduct, on_delete=models.CASCADE, null=True, blank=True)
    game_user_id = models.CharField(max_length=100, blank=True, null=True, help_text="Diperlukan untuk top-up")
    game_zone_id = models.CharField(max_length=50, blank=True, null=True, help_text="Diperlukan untuk beberapa game")
    
    quantity = models.PositiveIntegerField(default=1)
    harga_saat_ditambahkan = models.DecimalField(max_digits=10, decimal_places=2, help_text="Harga saat item ditambahkan ke cart")
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.item_type == 'AKUN' and self.akun:
            return f"{self.akun.nama_akun} x{self.quantity} di cart {self.cart.user.username}"
        elif self.item_type == 'TOPUP' and self.topup_product:
            return f"{self.topup_product.nama_paket} x{self.quantity} di cart {self.cart.user.username}"
        return f"CartItem {self.id}"

    def get_total_price(self):
        """Menghitung total harga item (harga * quantity)"""
        return self.harga_saat_ditambahkan * self.quantity

    def clean(self):
        """Validasi: pastikan hanya salah satu (akun atau topup_product) yang diisi"""
        from django.core.exceptions import ValidationError
        if self.item_type == 'AKUN' and not self.akun:
            raise ValidationError('Akun harus diisi untuk item type AKUN')
        if self.item_type == 'TOPUP' and not self.topup_product:
            raise ValidationError('TopUp Product harus diisi untuk item type TOPUP')
        if self.item_type == 'AKUN' and self.topup_product:
            raise ValidationError('Tidak bisa memiliki akun dan topup_product sekaligus')
        if self.item_type == 'TOPUP' and self.akun:
            raise ValidationError('Tidak bisa memiliki akun dan topup_product sekaligus')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'akun'],
                condition=models.Q(item_type='AKUN'),
                name='unique_akun_in_cart'
            ),
        ]

class CartOrder(models.Model):
    """Model untuk menyimpan order dari cart (untuk combined transaction)"""
    PAYMENT_METHOD_CHOICES = [
        ('MIDTRANS', 'Midtrans'),
        ('CRYPTO_USDT', 'USDT'),
        ('CRYPTO_ETH', 'Ethereum (ETH)'),
        ('CRYPTO_SOL', 'Solana (SOL)'),
    ]
    STATUS_CHOICES = [('PENDING', 'Pending'), ('COMPLETED', 'Completed'), ('CANCELED', 'Canceled')]
    
    pembeli = models.ForeignKey(User, on_delete=models.CASCADE)
    kode_transaksi = models.CharField(max_length=50, default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    harga_total = models.DecimalField(max_digits=10, decimal_places=2)
    kupon = models.ForeignKey(Kupon, on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='MIDTRANS')
    midtrans_token = models.CharField(max_length=255, null=True, blank=True)
    # Crypto payment fields
    crypto_address = models.CharField(max_length=255, null=True, blank=True, help_text="Wallet address untuk crypto payment")
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, help_text="Jumlah crypto yang harus dibayar")
    crypto_currency = models.CharField(max_length=10, null=True, blank=True, help_text="Currency code (USDT, ETH, SOL)")
    crypto_tx_hash = models.CharField(max_length=255, null=True, blank=True, help_text="Transaction hash setelah pembayaran")
    crypto_confirmed_at = models.DateTimeField(null=True, blank=True, help_text="Waktu konfirmasi pembayaran crypto")
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.kode_transaksi or isinstance(self.kode_transaksi, uuid.UUID) or (isinstance(self.kode_transaksi, str) and not self.kode_transaksi.startswith('CART-')):
            if isinstance(self.kode_transaksi, uuid.UUID):
                self.kode_transaksi = f"CART-{self.kode_transaksi}"
            else:
                import uuid as uuid_lib
                self.kode_transaksi = f"CART-{uuid_lib.uuid4()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cart Order {self.kode_transaksi} oleh {self.pembeli.username}"

    class Meta:
        verbose_name = "Cart Order"
        verbose_name_plural = "Cart Orders"

class CartOrderItem(models.Model):
    """Model untuk menyimpan item-item dalam cart order"""
    ITEM_TYPE_CHOICES = [
        ('AKUN', 'Akun Gaming'),
        ('TOPUP', 'Top Up'),
    ]
    
    cart_order = models.ForeignKey(CartOrder, on_delete=models.CASCADE, related_name='order_items')
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES)
    
    # Untuk item type AKUN
    akun = models.ForeignKey(AkunGaming, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Untuk item type TOPUP
    topup_product = models.ForeignKey(TopUpProduct, on_delete=models.SET_NULL, null=True, blank=True)
    game_user_id = models.CharField(max_length=100, blank=True, null=True)
    game_zone_id = models.CharField(max_length=50, blank=True, null=True)
    
    quantity = models.PositiveIntegerField(default=1)
    harga_saat_ditambahkan = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Reference ke pembelian yang dibuat setelah payment success (gunakan string untuk forward reference)
    pembelian_akun = models.ForeignKey('Pembelian', on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_order_item')
    pembelian_topup = models.ForeignKey('TopUpPembelian', on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_order_item')

    def __str__(self):
        if self.item_type == 'AKUN' and self.akun:
            return f"{self.akun.nama_akun} x{self.quantity} di order {self.cart_order.kode_transaksi}"
        elif self.item_type == 'TOPUP' and self.topup_product:
            return f"{self.topup_product.nama_paket} x{self.quantity} di order {self.cart_order.kode_transaksi}"
        return f"CartOrderItem {self.id}"

    def get_total_price(self):
        return self.harga_saat_ditambahkan * self.quantity

    class Meta:
        verbose_name = "Cart Order Item"
        verbose_name_plural = "Cart Order Items"