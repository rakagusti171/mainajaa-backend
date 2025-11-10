from rest_framework import serializers
from django.contrib.auth.models import User
from django.conf import settings
from cryptography.fernet import Fernet
from .models import AkunGaming, TopUpProduct, Pembelian, Kupon, TopUpPembelian, AkunGamingImage, Cart, CartItem, CartOrder, CartOrderItem
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
    gambar = serializers.SerializerMethodField()
    
    class Meta:
        model = AkunGamingImage
        fields = ['id', 'gambar']
    
    def get_gambar(self, obj):
        if obj.gambar:
            try:
                url = obj.gambar.url
                # Jika URL sudah absolute (Cloudinary), langsung return
                if url.startswith('http://') or url.startswith('https://'):
                    return url
                # Jika relative URL (local), buat absolute dengan request context
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(url)
                # Fallback jika tidak ada request context
                return url
            except Exception:
                return None
        return None

class AkunGamingSerializer(serializers.ModelSerializer):
    is_favorited = serializers.SerializerMethodField()
    images = AkunGamingImageSerializer(many=True, read_only=True)
    gambar = serializers.SerializerMethodField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = AkunGaming
        fields = ['id', 'nama_akun', 'game', 'deskripsi', 'harga', 'gambar',
                  'level', 'is_sold', 'stock', 'is_available', 'is_favorited', 'images']

    def get_gambar(self, obj):
        if obj.gambar:
            try:
                url = obj.gambar.url
                # Jika URL sudah absolute (Cloudinary), langsung return
                if url.startswith('http://') or url.startswith('https://'):
                    return url
                # Jika relative URL (local), buat absolute dengan request context
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(url)
                # Fallback jika tidak ada request context
                return url
            except Exception:
                return None
        return None

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
    gambar = serializers.SerializerMethodField()
    
    class Meta:
        model = TopUpProduct
        fields = ['id', 'game', 'nama_paket', 'harga', 'gambar']
    
    def get_gambar(self, obj):
        if obj.gambar:
            try:
                url = obj.gambar.url
                # Jika URL sudah absolute (Cloudinary), langsung return
                if url.startswith('http://') or url.startswith('https://'):
                    return url
                # Jika relative URL (local), buat absolute dengan request context
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(url)
                # Fallback jika tidak ada request context
                return url
            except Exception:
                return None
        return None

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
    
    # Crypto payment fields
    payment_method = serializers.ReadOnlyField()
    crypto_address = serializers.ReadOnlyField()
    crypto_amount = serializers.ReadOnlyField()
    crypto_currency = serializers.ReadOnlyField()
    crypto_tx_hash = serializers.ReadOnlyField()
    crypto_confirmed_at = serializers.ReadOnlyField()
    
    class Meta:
        model = Pembelian
        fields = [
            'id', 'kode_transaksi', 'tipe', 'nama_item', 'total', 'status', 'tanggal',
            'pembeli_username', 'harga_asli', 'kupon', 'rating', 'ulasan',
            'akun_email_decrypted', 'akun_password_decrypted',
            'payment_method', 'midtrans_token',
            'crypto_address', 'crypto_amount', 'crypto_currency', 'crypto_tx_hash', 'crypto_confirmed_at'
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

class CartItemSerializer(serializers.ModelSerializer):
    """Serializer untuk CartItem"""
    akun_detail = serializers.SerializerMethodField()
    topup_product_detail = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'item_type', 'akun', 'akun_detail', 'topup_product', 'topup_product_detail',
            'game_user_id', 'game_zone_id', 'quantity', 'harga_saat_ditambahkan', 'total_price', 'dibuat_pada'
        ]
        read_only_fields = ['harga_saat_ditambahkan', 'dibuat_pada']
    
    def get_akun_detail(self, obj):
        """Get akun detail dengan request context"""
        if obj.akun:
            request = self.context.get('request')
            return AkunGamingSerializer(obj.akun, context={'request': request}).data
        return None
    
    def get_topup_product_detail(self, obj):
        """Get topup product detail dengan request context"""
        if obj.topup_product:
            request = self.context.get('request')
            return TopUpProductSerializer(obj.topup_product, context={'request': request}).data
        return None
    
    def get_total_price(self, obj):
        return float(obj.get_total_price())
    
    def validate(self, data):
        """Validasi data sebelum create/update"""
        item_type = data.get('item_type')
        akun = data.get('akun')
        topup_product = data.get('topup_product')
        game_user_id = data.get('game_user_id')
        
        if item_type == 'AKUN':
            if not akun:
                raise serializers.ValidationError({'akun': 'Akun harus diisi untuk item type AKUN'})
            # Check if akun is sold (if akun is an instance)
            if hasattr(akun, 'is_sold') and akun.is_sold:
                raise serializers.ValidationError({'akun': 'Akun ini sudah terjual'})
        elif item_type == 'TOPUP':
            if not topup_product:
                raise serializers.ValidationError({'topup_product': 'TopUp Product harus diisi untuk item type TOPUP'})
            if not game_user_id:
                raise serializers.ValidationError({'game_user_id': 'Game User ID harus diisi untuk top-up'})
        
        return data
    
    def create(self, validated_data):
        """Override create untuk set harga_saat_ditambahkan"""
        item_type = validated_data.get('item_type')
        cart = validated_data.get('cart')
        
        # Set harga berdasarkan item type
        if item_type == 'AKUN' and validated_data.get('akun'):
            validated_data['harga_saat_ditambahkan'] = validated_data['akun'].harga
        elif item_type == 'TOPUP' and validated_data.get('topup_product'):
            validated_data['harga_saat_ditambahkan'] = validated_data['topup_product'].harga
        
        # Check if item already exists in cart
        if item_type == 'AKUN':
            existing_item = CartItem.objects.filter(cart=cart, akun=validated_data.get('akun')).first()
            if existing_item:
                # Update quantity instead of creating new
                existing_item.quantity += validated_data.get('quantity', 1)
                existing_item.save()
                return existing_item
        
        return super().create(validated_data)

class CartSerializer(serializers.ModelSerializer):
    """Serializer untuk Cart"""
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total_price', 'item_count', 'dibuat_pada', 'diperbarui_pada']
        read_only_fields = ['user', 'dibuat_pada', 'diperbarui_pada']
    
    def get_total_price(self, obj):
        return float(obj.get_total_price())
    
    def get_item_count(self, obj):
        return obj.get_item_count()