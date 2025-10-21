from rest_framework import serializers
from django.contrib.auth.models import User
from django.conf import settings
from cryptography.fernet import Fernet
from .models import AkunGaming, TopUpProduct, Pembelian, Kupon, TopUpPembelian, AkunGamingImage
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import password_validation

def decrypt_data(encrypted_data):
    """Mendekripsi data menggunakan FERNET_KEY."""
    if not encrypted_data:
        return None
    try:
        f = Fernet(settings.FERNET_KEY)
        return f.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        print(f"Decryption Error: {e}")
        return "Gagal Mendekripsi Data"
    
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        token['is_staff'] = user.is_staff
        return token

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_old_password(self, value):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("Konteks serializer tidak valid.")
        user = request.user
        if not user.is_authenticated:
            raise serializers.ValidationError("User tidak terautentikasi.")
        if not user.check_password(value):
            raise serializers.ValidationError("Password lama Anda salah.")
        return value

    def validate_new_password(self, value):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("Konteks serializer tidak valid.")
        user = request.user
        if not user.is_authenticated:
            raise serializers.ValidationError("User tidak terautentikasi.")
        password_validation.validate_password(value, user)
        return value

    def save(self, **kwargs):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError("Konteks serializer tidak valid.")
        user = request.user
        if not user.is_authenticated:
            raise serializers.ValidationError("User tidak terautentikasi.")
        new_password = self.validated_data.get('new_password')
        if new_password:
            user.set_password(new_password)
            user.save()
        return user

class AkunGamingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AkunGamingImage
        fields = ['id', 'gambar']

class AkunGamingSerializer(serializers.ModelSerializer):
    is_favorited = serializers.SerializerMethodField()
    images = AkunGamingImageSerializer(many=True, read_only=True)

    class Meta:
        model = AkunGaming
        fields = ['id', 'nama_akun', 'game', 'deskripsi', 'harga', 'gambar',
                  'level', 'is_sold', 'is_favorited', 'images']

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return obj.favorited_by.filter(pk=request.user.pk).exists()
        return False

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, label="Confirm Password")

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        # Validasi tambahan (misal: email unik) bisa ditambahkan di sini jika model User default tidak cukup
        if User.objects.filter(email=attrs['email']).exists():
             raise serializers.ValidationError({"email": "Email sudah terdaftar."})
        return attrs

    def create(self, validated_data) -> User:
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class PembelianSerializer(serializers.ModelSerializer):
    pembeli_username = serializers.ReadOnlyField(source='pembeli.username')
    nama_akun = serializers.ReadOnlyField(source='akun.nama_akun', default='Akun Dihapus')
    # Tambahkan relasi kupon agar bisa ditampilkan jika ada
    kupon_kode = serializers.ReadOnlyField(source='kupon.kode', default=None)

    class Meta:
        model = Pembelian
        fields = [
            'id', 'kode_transaksi', 'pembeli', 'pembeli_username', 'akun', 'nama_akun',
            'harga_total', 'harga_asli', 'kupon', 'kupon_kode', 'status',
            'dibuat_pada', 'midtrans_token', 'rating', 'ulasan'
        ]
        read_only_fields = ['kode_transaksi', 'pembeli', 'akun', 'dibuat_pada', 'midtrans_token', 'kupon']


class TopUpProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopUpProduct
        fields = ['id', 'game', 'nama_paket', 'harga', 'gambar']

class TopUpPembelianSerializer(serializers.ModelSerializer):
    produk = TopUpProductSerializer(read_only=True)
    pembeli_username = serializers.ReadOnlyField(source='pembeli.username')
    # Tambahkan relasi kupon agar bisa ditampilkan jika ada
    kupon_kode = serializers.ReadOnlyField(source='kupon.kode', default=None)

    class Meta:
        model = TopUpPembelian
        fields = [
            'id', 'kode_transaksi', 'pembeli', 'pembeli_username', 'produk',
            'game_user_id', 'game_zone_id', 'harga_pembelian', 'harga_asli',
            'kupon', 'kupon_kode','status', 'tanggal_pembelian', 'midtrans_token'
        ]
        read_only_fields = ['kode_transaksi', 'pembeli', 'produk', 'tanggal_pembelian', 'midtrans_token', 'kupon']


class UlasanSerializer(serializers.ModelSerializer):
    pembeli_username = serializers.CharField(source='pembeli.username', read_only=True)

    class Meta:
        model = Pembelian
        fields = ['pembeli_username', 'rating', 'ulasan', 'dibuat_pada']

class KuponAdminSerializer(serializers.ModelSerializer):
    jumlah_pengguna = serializers.SerializerMethodField()

    class Meta:
        model = Kupon
        fields = ['id', 'kode', 'diskon_persen', 'aktif', 'dibuat_pada', 'jumlah_pengguna']
        read_only_fields = ['dibuat_pada', 'jumlah_pengguna']

    def get_jumlah_pengguna(self, obj):
        return obj.digunakan_oleh.count()
    
# backend/api/serializers.py
# ... (serializer Anda yang lain) ...

# --- SERIALIZER BARU UNTUK RIWAYAT ---

class RiwayatAkunSerializer(serializers.ModelSerializer):
    """Serializer ramping untuk daftar riwayat pembelian AKUN."""
    tipe = serializers.SerializerMethodField()
    nama_item = serializers.ReadOnlyField(source='akun.nama_akun', default='Akun Dihapus')
    total = serializers.ReadOnlyField(source='harga_total')
    tanggal = serializers.ReadOnlyField(source='dibuat_pada')
    
    class Meta:
        model = Pembelian
        fields = ['id', 'kode_transaksi', 'tipe', 'nama_item', 'total', 'status', 'tanggal', 'midtrans_token']
        
    def get_tipe(self, obj):
        return 'Akun'

class RiwayatTopUpSerializer(serializers.ModelSerializer):
    """Serializer ramping untuk daftar riwayat pembelian TOP UP."""
    tipe = serializers.SerializerMethodField()
    nama_item = serializers.ReadOnlyField(source='produk.nama_paket', default='Produk Dihapus')
    total = serializers.ReadOnlyField(source='harga_pembelian')
    tanggal = serializers.ReadOnlyField(source='dibuat_pada') # Menggunakan @property dari model
    
    class Meta:
        model = TopUpPembelian
        fields = ['id', 'kode_transaksi', 'tipe', 'nama_item', 'total', 'status', 'tanggal', 'midtrans_token']

    def get_tipe(self, obj):
        return 'TopUp'

class PembelianDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detail untuk Pembelian AKUN.
    Menampilkan data akun yang sudah didekripsi.
    """
    tipe = serializers.SerializerMethodField()
    nama_item = serializers.ReadOnlyField(source='akun.nama_akun', default='Akun Dihapus')
    total = serializers.ReadOnlyField(source='harga_total')
    tanggal = serializers.ReadOnlyField(source='dibuat_pada')
    pembeli_username = serializers.ReadOnlyField(source='pembeli.username')
    
    # Kredensial Akun yang Didekripsi
    akun_email_decrypted = serializers.SerializerMethodField()
    akun_password_decrypted = serializers.SerializerMethodField()
    
    class Meta:
        model = Pembelian
        fields = [
            'id', 'kode_transaksi', 'tipe', 'nama_item', 'total', 'status', 'tanggal',
            'pembeli_username', 'harga_asli', 'kupon', 'rating', 'ulasan',
            'akun_email_decrypted', 'akun_password_decrypted'
        ]
    
    def get_tipe(self, obj):
        return 'Akun'
        
    def get_akun_email_decrypted(self, obj):
        if obj.status == 'COMPLETED' and obj.akun:
            return decrypt_data(obj.akun.akun_email)
        return "Tersedia setelah pembayaran lunas"

    def get_akun_password_decrypted(self, obj):
        if obj.status == 'COMPLETED' and obj.akun:
            return decrypt_data(obj.akun.akun_password)
        return "Tersedia setelah pembayaran lunas"