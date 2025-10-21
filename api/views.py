import json
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.views.decorators.csrf import csrf_exempt
from cryptography.fernet import Fernet
from decimal import Decimal
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth import password_validation
from django.core.mail import send_mail
from .models import (
    Kupon, AkunGaming, TopUpProduct, Pembelian, TopUpPembelian, 
    AkunGamingImage, 
)
from .serializers import (
    MyTokenObtainPairSerializer, ChangePasswordSerializer, 
    AkunGamingSerializer, TopUpProductSerializer, PembelianSerializer,
    TopUpPembelianSerializer, UlasanSerializer, RegisterSerializer, KuponAdminSerializer,
    RiwayatAkunSerializer, RiwayatTopUpSerializer,PembelianDetailSerializer,AkunGamingSerializer,
)

# ===================================================================
# FUNGSI HELPER
# ===================================================================

def decrypt_data(encrypted_data):
    if encrypted_data is None: return None
    try:
        f = Fernet(settings.FERNET_KEY)
        return f.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        print(f"Error decrypting data: {e}")
        return "Decryption Error"
    
def encrypt_data(data):
    """Mengenkripsi data menggunakan FERNET_KEY."""
    if not data:
        return None
    try:
        f = Fernet(settings.FERNET_KEY)
        return f.encrypt(data.encode()).decode()
    except Exception as e:
        print(f"Encryption Error: {e}")
        return None # Kembalikan None jika gagal
# --- SELESAI PENAMBAHAN ---
# ===================================================================
# AUTENTIKASI & USER VIEWS
# ===================================================================

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def registerUser(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = MyTokenObtainPairSerializer.get_token(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    model = User
    permission_classes = [IsAuthenticated]

    def get_object(self, queryset=None):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Password lama salah."]}, status=status.HTTP_400_BAD_REQUEST)
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            return Response({"status": "password set success"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ===================================================================
# PRODUK & TOP UP VIEWS (PUBLIK)
# ===================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def akun_gaming_list(request):
    queryset = AkunGaming.objects.filter(is_sold=False).order_by('-dibuat_pada')
    game_filter = request.query_params.get('game', None)
    if game_filter and game_filter != 'semua':
        queryset = queryset.filter(game=game_filter)
    sort_by = request.query_params.get('sort', 'terbaru')
    if sort_by == 'termurah':
        queryset = queryset.order_by('harga')
    elif sort_by == 'termahal':
        queryset = queryset.order_by('-harga')
    else:
        queryset = queryset.order_by('-dibuat_pada')
    serializer = AkunGamingSerializer(queryset, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def akun_gaming_detail(request, pk):
    akun = get_object_or_404(AkunGaming, pk=pk)
    serializer = AkunGamingSerializer(akun, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_similar_accounts(request, pk):
    current_akun = get_object_or_404(AkunGaming, pk=pk)
    similar_akuns = AkunGaming.objects.filter(game=current_akun.game, is_sold=False) \
                                       .exclude(pk=pk).order_by('?')[0:5]
    serializer = AkunGamingSerializer(similar_akuns, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_reviews_by_game(request, game_name):
    # PERBAIKAN DI SINI
    reviews = Pembelian.objects.filter(akun__game=game_name, status='COMPLETED', rating__isnull=False) \
                                .order_by('-dibuat_pada')
    serializer = UlasanSerializer(reviews, many=True) # <-- Menggunakan UlasanSerializer
    return Response(serializer.data)

class TopUpProductList(generics.ListAPIView):
    serializer_class = TopUpProductSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        queryset = TopUpProduct.objects.all().order_by('harga')
        game_filter = self.request.query_params.get('game', None)
        if game_filter and game_filter != 'semua':
            queryset = queryset.filter(game=game_filter)
        return queryset

class TopUpProductDetail(generics.RetrieveAPIView):
    queryset = TopUpProduct.objects.all()
    serializer_class = TopUpProductSerializer
    permission_classes = [AllowAny]
    lookup_field = 'pk'

# ===================================================================
# INTERAKSI USER (FAVORIT, RIWAYAT, ULASAN)
# ===================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_favorite(request, pk):
    akun = get_object_or_404(AkunGaming, pk=pk)
    if akun.favorited_by.filter(pk=request.user.pk).exists():
        akun.favorited_by.remove(request.user)
        favorited = False
    else:
        akun.favorited_by.add(request.user)
        favorited = True
    return Response({'favorited': favorited}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_favorit_akun(request):
    akuns = AkunGaming.objects.filter(favorited_by=request.user)
    serializer = AkunGamingSerializer(akuns, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pembelian_history(request):
    akun_purchases = Pembelian.objects.filter(pembeli=request.user).order_by('-dibuat_pada')
    topup_purchases = TopUpPembelian.objects.filter(pembeli=request.user).order_by('-tanggal_pembelian')
    akun_data = PembelianSerializer(akun_purchases, many=True).data
    topup_data = TopUpPembelianSerializer(topup_purchases, many=True).data
    combined_data = []
    for item in akun_data:
        item['tipe'] = 'akun'
        item['nama_item'] = item.get('nama_akun', 'Akun Dihapus')
        combined_data.append(item)
    for item in topup_data:
        item['tipe'] = 'topup'
        item['nama_item'] = item['produk']['nama_paket'] if item.get('produk') else 'Produk Dihapus'
        item['harga_total'] = item['harga_pembelian']
        item['dibuat_pada'] = item['tanggal_pembelian']
        combined_data.append(item)
    all_purchases = sorted(combined_data, key=lambda x: x['dibuat_pada'], reverse=True)
    return Response(all_purchases)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchase_detail(request, kode_transaksi):
    """
    Mengambil detail satu pesanan (Akun atau TopUp)
    berdasarkan kode_transaksi dan memastikan itu milik user.
    """
    user = request.user
    pembelian = None
    serializer = None
    
    try:
        if kode_transaksi.startswith('AKUN-'):
            # Ambil pembelian AKUN
            pembelian = Pembelian.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
            # Gunakan serializer detail yang bisa dekripsi
            serializer = PembelianDetailSerializer(pembelian)
            
        elif kode_transaksi.startswith('TOPUP-'):
            # Ambil pembelian TOP UP
            pembelian = TopUpPembelian.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
            # Gunakan serializer TopUp yang sudah ada (cukup detail)
            serializer = TopUpPembelianSerializer(pembelian) 
        
        else:
            return Response({'error': 'Format kode transaksi tidak valid.'}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(serializer.data)
        
    except (Pembelian.DoesNotExist, TopUpPembelian.DoesNotExist):
        return Response({'error': 'Pesanan tidak ditemukan atau bukan milik Anda.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error get_purchase_detail: {e}")
        return Response({'error': 'Terjadi kesalahan internal.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchase_detail(request, purchase_id):
    purchase = get_object_or_404(Pembelian, pk=purchase_id, pembeli=request.user)
    if purchase.status != 'COMPLETED':
        return Response({'error': 'Pembelian belum lunas'}, status=status.HTTP_403_FORBIDDEN)
    serializer = PembelianSerializer(purchase)
    data = serializer.data
    data['akun_email_decrypted'] = decrypt_data(purchase.akun.akun_email)
    data['akun_password_decrypted'] = decrypt_data(purchase.akun.akun_password)
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_review(request, purchase_id):
    purchase = get_object_or_404(Pembelian, pk=purchase_id, pembeli=request.user)
    if purchase.status != 'COMPLETED':
        return Response({'error': 'Pembelian belum lunas'}, status=status.HTTP_400_BAD_REQUEST)
    if purchase.rating is not None:
        return Response({'error': 'Ulasan sudah pernah diberikan'}, status=status.HTTP_400_BAD_REQUEST)
    purchase.rating = request.data.get('rating')
    purchase.ulasan = request.data.get('ulasan')
    purchase.save()
    return Response({'success': 'Ulasan berhasil disimpan'}, status=status.HTTP_201_CREATED)

# ===================================================================
# KUPON & PEMBAYARAN
# ===================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_coupon_api(request):
    kode_kupon = request.data.get('kode_kupon')
    account_id = request.data.get('account_id')

    # --- Print Statements for Debugging ---
    print(f"--- Validating AKUN coupon ---")
    print(f"Received kode: '{kode_kupon}' (Type: {type(kode_kupon)})")
    print(f"Received account_id: '{account_id}'")
    # --- End Print Statements ---

    if not kode_kupon or not account_id:
        print(">>> Validation failed: Missing kode_kupon or account_id") # Debug print
        return Response({'error': 'Kode kupon dan ID Akun dibutuhkan.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Mencari kupon yang cocok (case-insensitive) DAN aktif
        print(f">>> Querying Kupon: kode__iexact='{kode_kupon}', aktif=True") # Debug print
        kupon = Kupon.objects.get(kode__iexact=kode_kupon, aktif=True)
        print(f">>> Kupon found: {kupon.kode}") # Debug print
    except Kupon.DoesNotExist:
        # Gagal jika kode tidak cocok ATAU kupon tidak aktif
        print(f">>> Validation failed: Kupon '{kode_kupon}' not found or inactive.") # Debug print
        return Response({'valid': False, 'error': 'Kupon tidak valid.'}, status=status.HTTP_400_BAD_REQUEST)

    # Cek apakah kupon sudah digunakan oleh user ini
    print(f">>> Checking if user ID {request.user.id} used coupon ID {kupon.id}") # Debug print
    if kupon.digunakan_oleh.filter(id=request.user.id).exists():
        print(f">>> Validation failed: User {request.user.id} already used coupon {kupon.kode}.") # Debug print
        return Response({'valid': False, 'error': 'Kupon ini sudah pernah Anda gunakan.'}, status=status.HTTP_400_BAD_REQUEST)

    # Cek apakah akun ada dan belum terjual
    try:
        print(f">>> Querying AkunGaming: pk='{account_id}', is_sold=False") # Debug print
        akun = AkunGaming.objects.get(pk=account_id, is_sold=False)
        print(f">>> Account found: {akun.nama_akun}") # Debug print
    except AkunGaming.DoesNotExist:
        # Gagal jika akun tidak ditemukan ATAU sudah terjual
        print(f">>> Validation failed: AkunGaming with pk={account_id} and is_sold=False not found.") # Debug print
        # Mengembalikan error "Kupon tidak valid" agar frontend konsisten (meski masalahnya di akun)
        return Response({'valid': False, 'error': 'Kupon tidak valid.'}, status=status.HTTP_400_BAD_REQUEST) # <-- Pesan ini mungkin menyesatkan jika akun sudah sold

    # Jika semua pengecekan lolos, hitung diskon
    print(f">>> All checks passed for coupon {kupon.kode}. Calculating discount...") # Debug print
    harga_asli = akun.harga
    diskon = (harga_asli * Decimal(kupon.diskon_persen / 100))
    harga_final = harga_asli - diskon
    print(f">>> Discount calculated. Final price: {harga_final}") # Debug print

    # Kembalikan respons sukses
    return Response({
        'valid': True,
        'harga_asli': harga_asli,
        'diskon_amount': diskon,
        'harga_final': harga_final,
        'kode_kupon': kupon.kode # Kirim kode asli (dengan case dari db)
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_topup_coupon_api(request):
    kode_kupon = request.data.get('kode_kupon')
    product_id = request.data.get('product_id')
    if not kode_kupon or not product_id:
        return Response({'error': 'Kode kupon dan ID Produk dibutuhkan.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        kupon = Kupon.objects.get(kode__iexact=kode_kupon, aktif=True)
    except Kupon.DoesNotExist:
        return Response({'valid': False, 'error': 'Kupon tidak valid.'}, status=status.HTTP_400_BAD_REQUEST)
    if kupon.digunakan_oleh.filter(id=request.user.id).exists():
        return Response({'valid': False, 'error': 'Kupon ini sudah pernah Anda gunakan.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        produk = TopUpProduct.objects.get(pk=product_id)
    except TopUpProduct.DoesNotExist:
        return Response({'valid': False, 'error': 'Produk tidak ditemukan.'}, status=status.HTTP_400_BAD_REQUEST)

    harga_asli = produk.harga
    diskon = (harga_asli * Decimal(kupon.diskon_persen / 100))
    harga_final = harga_asli - diskon
    return Response({
        'valid': True, 'harga_asli': harga_asli, 'diskon_amount': diskon,
        'harga_final': harga_final, 'kode_kupon': kupon.kode
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_game_id_api(request):
    game = request.data.get('game')
    user_id = request.data.get('user_id')
    zone_id = request.data.get('zone_id')
    if game == 'Mobile Legends':
        if user_id == '12345' and zone_id == '1234':
            return Response({'nickname': 'PemainSakti_123'})
        else:
            return Response({'error': 'User ID atau Zone ID salah.'}, status=status.HTTP_400_BAD_REQUEST)
    if game == 'PUBG Mobile':
        if user_id == '55555':
            return Response({'nickname': 'SniperHandal_GG'})
        else:
            return Response({'error': 'User ID salah.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'error': 'Game tidak didukung untuk pengecekan ID.'}, status=status.HTTP_400_BAD_REQUEST)

# ===================================================================
# PEMBAYARAN & WEBHOOK MIDTRANS
# ===================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_pembelian(request):
    user = request.user
    data = request.data
    akun_id = data.get('akun_id')
    kode_kupon = data.get('kode_kupon', None)
    
    akun = get_object_or_404(AkunGaming, pk=akun_id)
    if akun.is_sold:
        return Response({'error': 'Akun sudah terjual'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        pembelian_obj, midtrans_token = Pembelian.create_pembelian(
            pembeli=user, akun=akun, kode_kupon_str=kode_kupon
        )

        try:
            subject = f'Pesanan [PENDING] - Kode: {pembelian_obj.kode_transaksi}'
            message = f"""
Halo {user.username},

Pesanan Anda untuk akun "{pembelian_obj.akun.nama_akun}" telah berhasil dibuat dengan kode transaksi:
{pembelian_obj.kode_transaksi}

Total Tagihan: Rp {pembelian_obj.harga_total:,.0f}

Pesanan ini sekarang menunggu pembayaran Anda.
Anda dapat melihat status pesanan dan melanjutkan pembayaran kapan saja melalui halaman Profil Anda.

Terima kasih,
Tim MainAjaa
            """
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            print(f"Email konfirmasi pesanan (pending) dikirim ke {user.email} for order {pembelian_obj.kode_transaksi}")
        except Exception as e:
            print(f"ERROR: Gagal mengirim email konfirmasi pesanan (pending) ke {user.email}: {e}")

        return Response({'midtrans_token': midtrans_token, 'pembelian_id': pembelian_obj.id})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_topup_pembelian(request):
    user = request.user
    data = request.data
    produk_id = data.get('produk_id')
    game_user_id = data.get('game_user_id')
    game_zone_id = data.get('game_zone_id', None)
    kode_kupon = data.get('kode_kupon', None)

    try:
        produk = get_object_or_404(TopUpProduct, pk=produk_id)
    except Exception as e:
         return Response({'error': f'Produk dengan ID {produk_id} tidak ditemukan.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        pembelian_obj, midtrans_token = TopUpPembelian.create_pembelian_topup(
            pembeli=user,
            produk=produk,
            game_user_id=game_user_id,
            game_zone_id=game_zone_id,
            kode_kupon_str=kode_kupon
        )
        try:
            subject = f'Pesanan Top Up [PENDING] - Kode: {pembelian_obj.kode_transaksi}'
            message = f"""
Halo {user.username},

Pesanan Top Up Anda untuk "{pembelian_obj.produk.nama_paket}" telah berhasil dibuat dengan kode transaksi:
{pembelian_obj.kode_transaksi}

Game ID: {pembelian_obj.game_user_id} {pembelian_obj.game_zone_id or ''}
Total Tagihan: Rp {pembelian_obj.harga_pembelian:,.0f}

Pesanan ini sekarang menunggu pembayaran Anda.
Anda dapat melihat status pesanan dan melanjutkan pembayaran kapan saja melalui halaman Profil Anda.

Terima kasih,
Tim MainAjaa
            """
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            print(f"Email konfirmasi top up (pending) dikirim ke {user.email} for order {pembelian_obj.kode_transaksi}")
        except Exception as e:
            print(f"ERROR: Gagal mengirim email konfirmasi top up (pending) ke {user.email}: {e}")

        return Response({'midtrans_token': midtrans_token, 'pembelian_id': pembelian_obj.id})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pembelian_history(request):
    """
    Mengambil gabungan riwayat pembelian Akun dan Top Up untuk user yang login,
    diurutkan berdasarkan tanggal terbaru.
    """
    user = request.user

    akun_history = Pembelian.objects.filter(pembeli=user)
    topup_history = TopUpPembelian.objects.filter(pembeli=user)
    akun_data = RiwayatAkunSerializer(akun_history, many=True).data
    topup_data = RiwayatTopUpSerializer(topup_history, many=True).data
    combined_history = list(akun_data) + list(topup_data)
    combined_history.sort(key=lambda x: str(x.get('tanggal')), reverse=True)
    
    return Response(combined_history)

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def midtrans_webhook(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        transaction_status = data.get('transaction_status')

        if not order_id or not transaction_status:
            return Response({'error': 'Data tidak valid'}, status=status.HTTP_400_BAD_REQUEST)

        # Tentukan tipe pembelian berdasarkan prefix
        pembelian = None
        if order_id.startswith('TOPUP-'):
            pembelian = get_object_or_404(TopUpPembelian, kode_transaksi=order_id)
        elif order_id.startswith('AKUN-'):
            pembelian = get_object_or_404(Pembelian, kode_transaksi=order_id)
        else:
            return Response({'error': 'Tipe order tidak dikenali'}, status=status.HTTP_400_BAD_REQUEST)

        if transaction_status == 'capture' or transaction_status == 'settlement':
            # Hanya proses jika statusnya masih PENDING
            if pembelian.status == 'PENDING':
                pembelian.status = 'COMPLETED'
                
                subject = ''
                message = ''
                
                # --- LOGIKA EMAIL LUNAS DIMULAI ---
                if isinstance(pembelian, Pembelian) and pembelian.akun:
                    # Ini adalah pembelian AKUN
                    pembelian.akun.is_sold = True
                    pembelian.akun.save()
                    print(f"Akun ID {pembelian.akun.id} marked as sold for order {order_id}")

                    # Dekripsi data akun untuk dikirim
                    akun_email_dec = decrypt_data(pembelian.akun.akun_email)
                    akun_pass_dec = decrypt_data(pembelian.akun.akun_password)

                    subject = f'Pesanan LUNAS - Kode: {pembelian.kode_transaksi}'
                    message = f"""
Halo {pembelian.pembeli.username},

Pembayaran Anda untuk pesanan {pembelian.kode_transaksi} ({pembelian.akun.nama_akun}) telah berhasil!

Berikut adalah detail data akun yang Anda beli:
----------------------------------
Email/Username Akun: {akun_email_dec}
Password Akun: {akun_pass_dec}
----------------------------------

Harap segera amankan akun Anda. Data ini juga dapat diakses melalui halaman 'Riwayat Pesanan' di profil Anda (setelah kami menyiapkannya).

Terima kasih telah berbelanja,
Tim MainAjaa
                    """

                elif isinstance(pembelian, TopUpPembelian):
                    # Ini adalah pembelian TOP UP
                    subject = f'Pesanan Top Up LUNAS - Kode: {pembelian.kode_transaksi}'
                    message = f"""
Halo {pembelian.pembeli.username},

Pembayaran Anda untuk pesanan Top Up {pembelian.kode_transaksi} ({pembelian.produk.nama_paket}) telah berhasil!

Top up Anda akan segera kami proses ke:
Game ID: {pembelian.game_user_id} {pembelian.game_zone_id or ''}

Terima kasih telah berbelanja,
Tim MainAjaa
                    """


                try:
                    if subject and message:
                        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [pembelian.pembeli.email], fail_silently=False)
                        print(f"Email konfirmasi LUNAS dikirim ke {pembelian.pembeli.email} for order {order_id}")
                except Exception as e:
                    print(f"ERROR: Gagal mengirim email LUNAS ke {pembelian.pembeli.email}: {e}")

                if pembelian.kupon:
                    pembelian.kupon.digunakan_oleh.add(pembelian.pembeli)

        elif transaction_status == 'pending':
            pass

        elif transaction_status == 'cancel' or transaction_status == 'expire' or transaction_status == 'deny':
            if pembelian.status == 'PENDING':
                pembelian.status = 'CANCELED'
                if isinstance(pembelian, Pembelian) and pembelian.akun:
                    pembelian.akun.is_sold = False
                    pembelian.akun.save()
                    print(f"Akun ID {pembelian.akun.id} marked as NOT sold (reverted) for order {order_id}")

        pembelian.save()
        return Response({'status': 'success'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error processing Midtrans webhook: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===================================================================
# ADMIN DASHBOARD VIEWS
# ===================================================================

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_get_all_orders(request):
    akun_purchases = Pembelian.objects.all().order_by('-dibuat_pada')
    topup_purchases = TopUpPembelian.objects.all().order_by('-tanggal_pembelian')
    akun_data = PembelianSerializer(akun_purchases, many=True).data
    topup_data = TopUpPembelianSerializer(topup_purchases, many=True).data
    combined_data = []
    for item in akun_data:
        item['tipe'] = 'AKUN'
        item['nama_item'] = item['nama_akun'] if item['nama_akun'] else 'N/A'
        combined_data.append(item)
    for item in topup_data:
        item['tipe'] = 'TOPUP'
        item['nama_item'] = item['produk']['nama_paket'] if item['produk'] else 'N/A'
        item['harga_total'] = item['harga_pembelian']
        item['dibuat_pada'] = item['tanggal_pembelian']
        combined_data.append(item)
    all_orders = sorted(combined_data, key=lambda x: x['dibuat_pada'], reverse=True)
    return Response(all_orders)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_dashboard_stats(request):
    akun_tersedia = AkunGaming.objects.filter(is_sold=False).count()
    akun_terjual = AkunGaming.objects.filter(is_sold=True).count()
    topup_berhasil = TopUpPembelian.objects.filter(status='COMPLETED').count()
    revenue_akun = Pembelian.objects.filter(status='COMPLETED').aggregate(total=Sum('harga_total'))['total'] or 0
    revenue_topup = TopUpPembelian.objects.filter(status='COMPLETED').aggregate(total=Sum('harga_pembelian'))['total'] or 0
    total_revenue = float(revenue_akun) + float(revenue_topup)
    stats_data = {
        'akun_tersedia': akun_tersedia, 'akun_terjual': akun_terjual,
        'topup_berhasil': topup_berhasil, 'total_revenue': total_revenue,
    }
    return Response(stats_data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_get_all_products(request):
    tipe_filter = request.query_params.get('tipe', 'semua')
    game_filter = request.query_params.get('game', 'semua')
    combined_data = []
    if tipe_filter == 'semua' or tipe_filter == 'AKUN':
        akun_queryset = AkunGaming.objects.all().order_by('-dibuat_pada')
        if game_filter and game_filter != 'semua':
            akun_queryset = akun_queryset.filter(game=game_filter)
        akun_data = AkunGamingSerializer(akun_queryset, many=True, context={'request': request}).data
        for item in akun_data:
            item['tipe'] = 'AKUN'
            item['nama_item'] = item['nama_akun']
            item['status_jual'] = 'TERJUAL' if item['is_sold'] else 'TERSEDIA'
            combined_data.append(item)
    if tipe_filter == 'semua' or tipe_filter == 'TOPUP':
        topup_queryset = TopUpProduct.objects.all().order_by('-id')
        if game_filter and game_filter != 'semua':
            topup_queryset = topup_queryset.filter(game=game_filter)
        topup_data = TopUpProductSerializer(topup_queryset, many=True).data
        for item in topup_data:
            item['tipe'] = 'TOPUP'
            item['nama_item'] = item['nama_paket']
            item['harga'] = item['harga']
            item['status_jual'] = 'TERSEDIA'
            combined_data.append(item)
    all_products = sorted(combined_data, key=lambda x: x['tipe'])
    return Response(all_products)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_delete_product(request):
    tipe = request.data.get('tipe')
    product_id = request.data.get('id')
    if not tipe or not product_id:
        return Response({'error': 'Tipe dan ID produk dibutuhkan.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        if tipe == 'AKUN':
            produk = get_object_or_404(AkunGaming, id=product_id)
        elif tipe == 'TOPUP':
            produk = get_object_or_404(TopUpProduct, id=product_id)
        else:
            return Response({'error': 'Tipe produk tidak valid.'}, status=status.HTTP_400_BAD_REQUEST)
        produk.delete()
        return Response({'success': 'Produk berhasil dihapus.'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAdminUser])
@transaction.atomic
def admin_create_akun(request):
    """
    Membuat AkunGaming baru dari dashboard admin.
    Termasuk enkripsi kredensial akun.
    """
    # Ambil data dari form
    nama_akun = request.data.get('nama_akun')
    game = request.data.get('game')
    level = request.data.get('level')
    deskripsi = request.data.get('deskripsi')
    harga = request.data.get('harga')
    # --- TAMBAHKAN INI ---
    akun_email = request.data.get('akun_email')
    akun_password = request.data.get('akun_password')
    # --- Selesai ---

    gambar_cover = request.FILES.get('gambar')
    gambar_galeri = request.FILES.getlist('images[]')

    # Validasi (Tambahkan validasi kredensial)
    if not all([nama_akun, game, harga, gambar_cover, akun_email, akun_password]): # <-- Tambahkan akun_email & akun_password
        return Response({'error': 'Semua field bertanda * wajib diisi.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # --- Enkripsi Kredensial ---
        encrypted_email = encrypt_data(akun_email)
        encrypted_password = encrypt_data(akun_password)
        if not encrypted_email or not encrypted_password:
             raise ValueError("Gagal mengenkripsi kredensial akun.")
        # --- Selesai Enkripsi ---

        # Buat objek AkunGaming utama (Tambahkan kredensial terenkripsi)
        akun = AkunGaming.objects.create(
            nama_akun=nama_akun,
            game=game,
            level=level if level else 1,
            deskripsi=deskripsi,
            harga=harga,
            gambar=gambar_cover,
            akun_email=encrypted_email,       # <-- Tambahkan ini
            akun_password=encrypted_password # <-- Tambahkan ini
        )

        # Loop dan simpan semua gambar galeri (tidak berubah)
        for img_file in gambar_galeri:
            AkunGamingImage.objects.create(akun=akun, gambar=img_file)

        # Kembalikan data yang baru dibuat (tidak berubah)
        serializer = AkunGamingSerializer(akun, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        # --- PERUBAHAN ---
        # Cetak error aslinya ke terminal agar kita bisa lihat
        print("!!! TRACEBACK ERROR admin_create_akun:")
        print(e)
        # --- SELESAI PERUBAHAN ---
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_get_akun_detail(request, pk):
    try:
        akun = get_object_or_404(AkunGaming, pk=pk)
        serializer = AkunGamingSerializer(akun, context={'request': request})
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_4404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAdminUser])
@transaction.atomic
def admin_update_akun(request, pk):
    try:
        akun = get_object_or_404(AkunGaming, pk=pk)
        akun.nama_akun = request.data.get('nama_akun', akun.nama_akun)
        akun.game = request.data.get('game', akun.game)
        akun.level = request.data.get('level', akun.level)
        akun.deskripsi = request.data.get('deskripsi', akun.deskripsi)
        akun.harga = request.data.get('harga', akun.harga)
        if 'gambar' in request.FILES:
            akun.gambar = request.FILES.get('gambar')
        akun.save()
        gambar_galeri = request.FILES.getlist('images[]')
        for img_file in gambar_galeri:
            AkunGamingImage.objects.create(akun=akun, gambar=img_file)
        delete_image_ids = request.data.getlist('delete_images[]')
        if delete_image_ids:
            AkunGamingImage.objects.filter(id__in=delete_image_ids, akun=akun).delete()
        serializer = AkunGamingSerializer(akun, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_create_topup(request):
    """
    Membuat TopUpProduct baru dari dashboard admin.
    Menerima 'multipart/form-data'.
    """
    # Ambil data dari form
    game = request.data.get('game')
    nama_paket = request.data.get('nama_paket')
    harga = request.data.get('harga')
    gambar = request.FILES.get('gambar') 

    # Validasi sederhana
    if not all([game, nama_paket, harga, gambar]):
        return Response({'error': 'Field Game, Nama Paket, Harga, dan Gambar wajib diisi.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        topup = TopUpProduct.objects.create(
            game=game,
            nama_paket=nama_paket,
            harga=harga,
            gambar=gambar
        )

        serializer = TopUpProductSerializer(topup, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_get_topup_detail(request, pk):
    """
    Mengambil data detail satu TopUpProduct untuk di-edit.
    """
    try:
        topup = get_object_or_404(TopUpProduct, pk=pk)
        serializer = TopUpProductSerializer(topup, context={'request': request})
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST']) # Pakai POST untuk multipart/form-data
@permission_classes([IsAdminUser])
def admin_update_topup(request, pk):
    """
    Menyimpan perubahan (update) pada TopUpProduct.
    """
    try:
        topup = get_object_or_404(TopUpProduct, pk=pk)

        # Ambil data dari form, gunakan data lama jika tidak ada yang baru
        topup.game = request.data.get('game', topup.game)
        topup.nama_paket = request.data.get('nama_paket', topup.nama_paket)
        topup.harga = request.data.get('harga', topup.harga)

        # Cek apakah ada gambar baru
        if 'gambar' in request.FILES:
            topup.gambar = request.FILES.get('gambar')

        topup.save() # Simpan perubahan

        serializer = TopUpProductSerializer(topup, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_get_all_coupons(request):
    """
    Mengambil semua kupon untuk tabel admin.
    """
    coupons = Kupon.objects.all().order_by('-dibuat_pada')
    serializer = KuponAdminSerializer(coupons, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_create_coupon(request):
    """
    Membuat Kupon baru.
    """
    kode = request.data.get('kode')
    diskon_persen = request.data.get('diskon_persen')
    aktif = request.data.get('aktif', True) # Default aktif

    # Validasi
    if not kode or not diskon_persen:
        return Response({'error': 'Kode dan Diskon Persen wajib diisi.'}, status=status.HTTP_400_BAD_REQUEST)
    if Kupon.objects.filter(kode__iexact=kode).exists():
        return Response({'error': 'Kode kupon sudah ada.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        diskon_value = int(diskon_persen)
        if not (1 <= diskon_value <= 100):
             raise ValueError("Diskon harus antara 1 dan 100.")
    except (ValueError, TypeError):
         return Response({'error': 'Diskon Persen harus berupa angka (1-100).'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        kupon = Kupon.objects.create(
            kode=kode.upper(), # Simpan sebagai uppercase
            diskon_persen=diskon_value,
            aktif=bool(aktif)
        )
        serializer = KuponAdminSerializer(kupon)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_toggle_coupon_active(request, pk):
    """
    Mengubah status aktif/nonaktif kupon.
    """
    try:
        kupon = get_object_or_404(Kupon, pk=pk)
        kupon.aktif = not kupon.aktif # Balik statusnya
        kupon.save()
        serializer = KuponAdminSerializer(kupon)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_topup_pembelian(request):
    user = request.user
    data = request.data
    print(">>> [VIEW] 1. Received data:", data) # Print 1

    produk_id = data.get('produk_id')
    game_user_id = data.get('game_user_id')
    game_zone_id = data.get('game_zone_id', None)
    kode_kupon = data.get('kode_kupon', None)

    # Pastikan produk ada sebelum melanjutkan
    try:
        produk = get_object_or_404(TopUpProduct, pk=produk_id)
        print(">>> [VIEW] 2. Product found:", produk) # Print 2
    except Exception as e:
         print(f">>> [VIEW] ERROR finding product: {e}")
         return Response({'error': f'Produk dengan ID {produk_id} tidak ditemukan.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        print(">>> [VIEW] 3. Calling TopUpPembelian.create_pembelian_topup...") # Print 3
        pembelian_obj, midtrans_token = TopUpPembelian.create_pembelian_topup(
            pembeli=user,
            produk=produk,
            game_user_id=game_user_id,
            game_zone_id=game_zone_id,
            kode_kupon_str=kode_kupon
        )
        # Jika berhasil sampai sini, print tokennya
        print(f">>> [VIEW] 4. Model method returned. Token: {midtrans_token}") # Print 4

        # Pastikan midtrans_token tidak None sebelum return
        if midtrans_token:
            print(">>> [VIEW] 5. Returning SUCCESS response.") # Print 5
            return Response({'midtrans_token': midtrans_token, 'pembelian_id': pembelian_obj.id})
        else:
            # Ini seharusnya tidak terjadi jika model melempar error
            print(">>> [VIEW] ERROR: midtrans_token is None after model call!")
            return Response({'error': 'Gagal memproses transaksi (token tidak diterima).'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        # Tangkap error APAPUN yang dilempar dari model
        print(f">>> [VIEW] 6. Caught exception in view: {type(e).__name__} - {e}") # Print 6
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Baris ini seharusnya TIDAK PERNAH tercapai
    print(">>> [VIEW] 7. ERROR: Reached end of view without returning!")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_favorite_accounts(request):
    """
    Mengambil semua akun yang difavoritkan oleh user yang sedang login.
    """
    user = request.user
    # Ambil semua akun yang difavoritkan oleh user ini DAN belum terjual
    favorit_akun = user.favorite_accounts.filter(is_sold=False).order_by('-dibuat_pada')

    # Gunakan serializer yang sama dengan list akun
    serializer = AkunGamingSerializer(favorit_akun, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Memulai proses reset password.
    Menerima email, mengirim link reset jika user ada.
    """
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email wajib diisi.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # PENTING: Jangan beritahu user bahwa email tidak ada.
        # Ini adalah praktik keamanan untuk mencegah email enumeration.
        return Response({'success': 'Jika email terdaftar, link reset telah dikirim.'}, status=status.HTTP_200_OK)

    # Buat token
    token_generator = PasswordResetTokenGenerator()
    token = token_generator.make_token(user)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

    # Buat link frontend
    # TODO: Ganti 'http://localhost:5173' dengan URL frontend Anda dari .env di produksi
    frontend_url = 'http://localhost:5173' 
    reset_link = f"{frontend_url}/reset-password/{uidb64}/{token}/"

    # Kirim email
    try:
        subject = 'Reset Password Akun MainAjaa Anda'
        message = f"""
Halo {user.username},

Kami menerima permintaan untuk mereset password akun Anda.
Silakan klik link di bawah ini untuk mengatur password baru:

{reset_link}

Jika Anda tidak meminta ini, abaikan saja email ini.

Salam,
Tim MainAjaa
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
        print(f"Email reset password dikirim ke {user.email}")
    except Exception as e:
        print(f"ERROR: Gagal mengirim email reset password: {e}")
        return Response({'error': 'Gagal mengirim email.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'success': 'Jika email terdaftar, link reset telah dikirim.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """
    Mengonfirmasi dan mengatur password baru.
    """
    uidb64 = request.data.get('uidb64')
    token = request.data.get('token')
    new_password = request.data.get('new_password')

    if not all([uidb64, token, new_password]):
        return Response({'error': 'Semua field (uid, token, password) wajib diisi.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Decode UID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Validasi token
    token_generator = PasswordResetTokenGenerator()
    if user is not None and token_generator.check_token(user, token):
        # Token valid, validasi password baru
        try:
            password_validation.validate_password(new_password, user)
        except Exception as e:
            return Response({'error': list(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # Set password baru
        user.set_password(new_password)
        user.save()
        return Response({'success': 'Password berhasil direset. Silakan login.'}, status=status.HTTP_200_OK)
    else:
        # Token tidak valid atau user tidak ada
        return Response({'error': 'Link reset tidak valid atau sudah kedaluwarsa.'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_review(request, purchase_id):
    """
    Menerima submit ulasan (rating & teks) untuk pembelian AKUN.
    """
    user = request.user
    data = request.data
    rating = data.get('rating')
    ulasan = data.get('ulasan', '') # Ulasan opsional

    if not rating:
        return Response({'error': 'Rating wajib diisi.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Cari pembelian berdasarkan ID (bukan kode_transaksi)
        pembelian = Pembelian.objects.get(id=purchase_id)
    except Pembelian.DoesNotExist:
        return Response({'error': 'Pembelian tidak ditemukan.'}, status=status.HTTP_404_NOT_FOUND)

    # Validasi
    if pembelian.pembeli != user:
        return Response({'error': 'Anda tidak bisa memberi ulasan untuk pesanan ini.'}, status=status.HTTP_403_FORBIDDEN)
    if pembelian.status != 'COMPLETED':
        return Response({'error': 'Anda hanya bisa memberi ulasan untuk pesanan yang lunas.'}, status=status.HTTP_400_BAD_REQUEST)
    if pembelian.rating is not None:
        return Response({'error': 'Anda sudah pernah memberi ulasan untuk pesanan ini.'}, status=status.HTTP_400_BAD_REQUEST)

    # Simpan ulasan
    try:
        pembelian.rating = int(rating)
        pembelian.ulasan = ulasan
        pembelian.save()
        
        # Kirim kembali data ulasan yang sudah disimpan (atau cukup sukses)
        return Response({
            'success': 'Ulasan berhasil dikirim!',
            'rating': pembelian.rating,
            'ulasan': pembelian.ulasan
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': f'Gagal menyimpan ulasan: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)