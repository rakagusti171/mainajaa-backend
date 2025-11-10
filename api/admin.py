# backend/api/admin.py

from django.contrib import admin
from django.conf import settings
from django.utils.html import format_html
from cryptography.fernet import Fernet

# --- 1. Import SEMUA model, termasuk AkunGamingImage ---
from .models import (
    AkunGaming, TopUpProduct, Pembelian, Kupon, TopUpPembelian, 
    AkunGamingImage, CartOrder, CartOrderItem
)

# --- Fungsi Helper Enkripsi ---
def encrypt_data(data):
    """Menerima string, mengembalikan string terenkripsi."""
    if data is None:
        return None
    try:
        f = Fernet(settings.FERNET_KEY)
        return f.encrypt(data.encode()).decode()
    except Exception as e:
        print(f"Error encrypting data: {e}")
        return None

# --- Admin Model ---

# 2. Class Inline untuk galeri gambar
class AkunGamingImageInline(admin.TabularInline):
    model = AkunGamingImage
    extra = 3 # Memberi 3 slot upload kosong

@admin.register(AkunGaming)
class AkunGamingAdmin(admin.ModelAdmin):
    list_display = ('nama_akun', 'game', 'harga', 'stock', 'is_sold', 'dibuat_pada')
    list_filter = ('game', 'is_sold')
    search_fields = ('nama_akun', 'game')
    
    fields = ('nama_akun', 'game', 'level', 'deskripsi', 'harga', 'gambar', 'stock', 'is_sold', 
              'akun_email', 'akun_password', 'favorited_by')
    
    readonly_fields = ('favorited_by',)
    
    # 3. Menambahkan inline ke AkunGamingAdmin
    inlines = [AkunGamingImageInline]
    
    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get('akun_email'):
             obj.akun_email = encrypt_data(form.cleaned_data['akun_email'])
        if form.cleaned_data.get('akun_password'):
            obj.akun_password = encrypt_data(form.cleaned_data['akun_password'])
            
        super().save_model(request, obj, form, change)

@admin.register(TopUpProduct)
class TopUpProductAdmin(admin.ModelAdmin):
    list_display = ('game', 'nama_paket', 'harga', 'stock', 'image_preview')
    list_filter = ('game',)
    search_fields = ('nama_paket',)
    fields = ('game', 'nama_paket', 'harga', 'gambar', 'stock')

    def image_preview(self, obj):
        if obj.gambar:
            return format_html('<img src="{}" style="max-height: 40px; max-width: 40px;" />', obj.gambar.url)
        return "(No image)"
    
    image_preview.short_description = 'Preview'

@admin.register(Pembelian)
class PembelianAdmin(admin.ModelAdmin):
    list_display = ('kode_transaksi', 'pembeli', 'akun', 'harga_total', 'payment_method', 'status', 'dibuat_pada')
    list_filter = ('status', 'payment_method', 'akun__game')
    search_fields = ('kode_transaksi', 'pembeli__username', 'akun__nama_akun', 'crypto_tx_hash')
    
    readonly_fields = ('kode_transaksi', 'pembeli', 'akun',
                       'harga_total', 'harga_asli', 'kupon', 'midtrans_token', 
                       'dibuat_pada', 'rating', 'ulasan', 'payment_method',
                       'crypto_address', 'crypto_amount', 'crypto_currency', 
                       'crypto_tx_hash', 'crypto_confirmed_at')
    
    fieldsets = (
        ('Informasi Transaksi', {
            'fields': ('kode_transaksi', 'pembeli', 'akun', 'status', 'dibuat_pada')
        }),
        ('Pembayaran', {
            'fields': ('payment_method', 'midtrans_token', 'harga_total', 'harga_asli', 'kupon')
        }),
        ('Crypto Payment', {
            'fields': ('crypto_address', 'crypto_amount', 'crypto_currency', 'crypto_tx_hash', 'crypto_confirmed_at'),
            'classes': ('collapse',)
        }),
        ('Review', {
            'fields': ('rating', 'ulasan')
        }),
    )

@admin.register(Kupon)
class KuponAdmin(admin.ModelAdmin):
    list_display = ('kode', 'diskon_persen', 'aktif', 'dibuat_pada')
    search_fields = ('kode',)
    list_filter = ('aktif',)
    filter_horizontal = ('digunakan_oleh',)

@admin.register(TopUpPembelian)
class TopUpPembelianAdmin(admin.ModelAdmin):
    list_display = ('kode_transaksi', 'pembeli', 'produk', 'game_user_id', 'harga_pembelian', 'status', 'tanggal_pembelian')
    list_filter = ('status', 'produk__game')
    search_fields = ('pembeli__username', 'game_user_id', 'kode_transaksi')
    
    readonly_fields = ('kode_transaksi', 'pembeli', 'produk', 'game_user_id', 
                       'game_zone_id', 'harga_pembelian', 'harga_asli', 
                       'kupon', 'midtrans_token', 'tanggal_pembelian')

@admin.register(CartOrder)
class CartOrderAdmin(admin.ModelAdmin):
    list_display = ('kode_transaksi', 'pembeli', 'harga_total', 'payment_method', 'status', 'dibuat_pada')
    list_filter = ('status', 'payment_method')
    search_fields = ('kode_transaksi', 'pembeli__username', 'crypto_tx_hash')
    
    readonly_fields = ('kode_transaksi', 'pembeli', 'harga_total', 'kupon', 
                       'payment_method', 'midtrans_token', 'dibuat_pada',
                       'crypto_address', 'crypto_amount', 'crypto_currency', 
                       'crypto_tx_hash', 'crypto_confirmed_at')
    
    fieldsets = (
        ('Informasi Order', {
            'fields': ('kode_transaksi', 'pembeli', 'status', 'dibuat_pada')
        }),
        ('Pembayaran', {
            'fields': ('payment_method', 'midtrans_token', 'harga_total', 'kupon')
        }),
        ('Crypto Payment', {
            'fields': ('crypto_address', 'crypto_amount', 'crypto_currency', 'crypto_tx_hash', 'crypto_confirmed_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(CartOrderItem)
class CartOrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart_order', 'item_type', 'akun', 'quantity', 'harga_saat_ditambahkan')
    list_filter = ('item_type', 'cart_order__status')
    search_fields = ('cart_order__kode_transaksi', 'akun__nama_akun')
    
    readonly_fields = ('cart_order', 'item_type', 'akun', 'topup_product', 
                       'game_user_id', 'game_zone_id', 'quantity', 
                       'harga_saat_ditambahkan', 'pembelian_akun', 'pembelian_topup')
