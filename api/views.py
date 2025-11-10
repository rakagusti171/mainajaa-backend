import json
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Count, Q, Avg
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
import midtransclient
import hashlib
snap = midtransclient.Snap(
    is_production=settings.MIDTRANS_IS_PRODUCTION,
    server_key=settings.MIDTRANS_SERVER_KEY,
    client_key=settings.MIDTRANS_CLIENT_KEY
)
from .models import (
    Kupon, AkunGaming, TopUpProduct, Pembelian, TopUpPembelian, 
    AkunGamingImage, Cart, CartItem, CartOrder, CartOrderItem,
)
from .serializers import (
    MyTokenObtainPairSerializer, ChangePasswordSerializer, 
    AkunGamingSerializer, TopUpProductSerializer, PembelianSerializer,
    TopUpPembelianSerializer, UlasanSerializer, RegisterSerializer, KuponAdminSerializer,
    RiwayatAkunSerializer, RiwayatTopUpSerializer,PembelianDetailSerializer,AkunGamingSerializer,
    CartSerializer, CartItemSerializer,
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
        return None 
    
def _buat_signature_key(order_id, status_code, gross_amount):
    """Membuat signature key untuk verifikasi webhook Midtrans"""
    server_key = settings.MIDTRANS_SERVER_KEY
    string_to_hash = f"{order_id}{status_code}{gross_amount}{server_key}"
    return hashlib.sha512(string_to_hash.encode()).hexdigest()
# ===================================================================
# AUTENTIKASI & USER VIEWS
# ===================================================================

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    permission_classes = [AllowAny]

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
    
    # Pagination support
    page = request.query_params.get('page', None)
    page_size = request.query_params.get('page_size', None)
    
    if page and page_size:
        try:
            page = int(page)
            page_size = int(page_size)
            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            paginated_queryset = queryset[start:end]
            
            serializer = AkunGamingSerializer(paginated_queryset, many=True, context={'request': request})
            return Response({
                'count': total_count,
                'next': f'{request.build_absolute_uri()}?page={page + 1}&page_size={page_size}' if end < total_count else None,
                'previous': f'{request.build_absolute_uri()}?page={page - 1}&page_size={page_size}' if start > 0 else None,
                'results': serializer.data
            })
        except (ValueError, TypeError):
            # If pagination params are invalid, return all results
            pass
    
    # Return all results if pagination not requested
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
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Pagination support
        page = request.query_params.get('page', None)
        page_size = request.query_params.get('page_size', None)
        
        if page and page_size:
            try:
                page = int(page)
                page_size = int(page_size)
                total_count = queryset.count()
                start = (page - 1) * page_size
                end = start + page_size
                paginated_queryset = queryset[start:end]
                
                serializer = self.get_serializer(paginated_queryset, many=True)
                return Response({
                    'count': total_count,
                    'next': f'{request.build_absolute_uri()}?page={page + 1}&page_size={page_size}' if end < total_count else None,
                    'previous': f'{request.build_absolute_uri()}?page={page - 1}&page_size={page_size}' if start > 0 else None,
                    'results': serializer.data
                })
            except (ValueError, TypeError):
                # If pagination params are invalid, return all results
                pass
        
        # Return all results if pagination not requested
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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
def download_invoice(request, kode_transaksi):
    """
    Download invoice PDF untuk pembelian.
    Support AKUN, TOPUP, dan CART order.
    """
    user = request.user
    
    try:
        pembelian_data = {}
        
        if kode_transaksi.startswith('CART-'):
            # Handle Cart Order
            cart_order = CartOrder.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
            
            items = []
            for order_item in cart_order.order_items.all():
                if order_item.item_type == 'AKUN' and order_item.akun:
                    items.append({
                        'nama': order_item.akun.nama_akun,
                        'game': order_item.akun.game,
                        'harga': float(order_item.harga_saat_ditambahkan),
                        'quantity': order_item.quantity,
                        'subtotal': float(order_item.get_total_price()),
                    })
            
            pembelian_data = {
                'kode_transaksi': cart_order.kode_transaksi,
                'tanggal': cart_order.dibuat_pada.strftime('%d %B %Y, %H:%M WIB'),
                'pembeli': {
                    'username': cart_order.pembeli.username,
                    'email': cart_order.pembeli.email,
                },
                'items': items,
                'subtotal': float(cart_order.harga_total),
                'diskon': 0,  # Diskon sudah dihitung di harga_total
                'total': float(cart_order.harga_total),
                'status': cart_order.status,
                'tipe': 'CART',
            }
            
        elif kode_transaksi.startswith('AKUN-'):
            # Handle single AKUN purchase
            pembelian = Pembelian.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
            
            items = []
            if pembelian.akun:
                items.append({
                    'nama': pembelian.akun.nama_akun,
                    'game': pembelian.akun.game,
                    'harga': float(pembelian.harga_asli or pembelian.akun.harga),
                    'quantity': 1,
                    'subtotal': float(pembelian.harga_total),
                })
            
            diskon = float(pembelian.harga_asli - pembelian.harga_total) if pembelian.harga_asli else 0
            
            pembelian_data = {
                'kode_transaksi': pembelian.kode_transaksi,
                'tanggal': pembelian.dibuat_pada.strftime('%d %B %Y, %H:%M WIB'),
                'pembeli': {
                    'username': pembelian.pembeli.username,
                    'email': pembelian.pembeli.email,
                },
                'items': items,
                'subtotal': float(pembelian.harga_asli or pembelian.harga_total),
                'diskon': diskon,
                'total': float(pembelian.harga_total),
                'status': pembelian.status,
                'tipe': 'AKUN',
            }
            
        elif kode_transaksi.startswith('TOPUP-'):
            # Handle single TOPUP purchase
            pembelian = TopUpPembelian.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
            
            items = []
            if pembelian.produk:
                items.append({
                    'nama': pembelian.produk.nama_paket,
                    'game': pembelian.produk.game,
                    'harga': float(pembelian.harga_asli or pembelian.produk.harga),
                    'quantity': 1,
                    'subtotal': float(pembelian.harga_pembelian),
                })
            
            diskon = float(pembelian.harga_asli - pembelian.harga_pembelian) if pembelian.harga_asli else 0
            
            pembelian_data = {
                'kode_transaksi': pembelian.kode_transaksi,
                'tanggal': pembelian.tanggal_pembelian.strftime('%d %B %Y, %H:%M WIB'),
                'pembeli': {
                    'username': pembelian.pembeli.username,
                    'email': pembelian.pembeli.email,
                },
                'items': items,
                'subtotal': float(pembelian.harga_asli or pembelian.harga_pembelian),
                'diskon': diskon,
                'total': float(pembelian.harga_pembelian),
                'status': pembelian.status,
                'tipe': 'TOPUP',
            }
        else:
            return Response({'error': 'Format kode transaksi tidak valid.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate and return PDF
        return create_invoice_response(pembelian_data)
        
    except (Pembelian.DoesNotExist, TopUpPembelian.DoesNotExist, CartOrder.DoesNotExist):
        return Response({'error': 'Pesanan tidak ditemukan atau bukan milik Anda.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error generating invoice: {e}")
        import traceback
        traceback.print_exc()
        return Response({'error': f'Gagal generate invoice: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_crypto_payment(request):
    """
    Verify crypto payment dengan transaction hash.
    Admin perlu verifikasi manual untuk saat ini.
    """
    user = request.user
    data = request.data
    kode_transaksi = data.get('kode_transaksi')
    tx_hash = data.get('tx_hash')
    
    if not kode_transaksi or not tx_hash:
        return Response({'error': 'Kode transaksi dan transaction hash diperlukan.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Find order (Pembelian or CartOrder)
        pembelian = None
        cart_order = None
        
        if kode_transaksi.startswith('CART-'):
            cart_order = CartOrder.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
        elif kode_transaksi.startswith('AKUN-'):
            pembelian = Pembelian.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
        else:
            return Response({'error': 'Format kode transaksi tidak valid.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update transaction hash and verify payment
        if cart_order:
            cart_order.crypto_tx_hash = tx_hash
            cart_order.save()
            
            # Try to verify payment automatically
            from .crypto_payment import verify_crypto_payment
            is_verified, confirmations, error_msg = verify_crypto_payment(
                tx_hash, 
                cart_order.crypto_currency, 
                cart_order.crypto_amount, 
                cart_order.crypto_address
            )
            
            if is_verified and confirmations >= 1:  # At least 1 confirmation
                # Auto-verify if transaction is confirmed
                cart_order.status = 'COMPLETED'
                cart_order.crypto_confirmed_at = timezone.now()
                cart_order.save()
                
                # Create individual Pembelian records for each item
                for order_item in cart_order.order_items.all():
                    try:
                        if order_item.item_type == 'AKUN' and order_item.akun:
                            pembelian_akun = Pembelian.objects.create(
                                pembeli=cart_order.pembeli,
                                akun=order_item.akun,
                                harga_total=order_item.get_total_price(),
                                harga_asli=order_item.harga_saat_ditambahkan,
                                kupon=cart_order.kupon,
                                status='COMPLETED',
                                payment_method=cart_order.payment_method,
                                crypto_tx_hash=tx_hash,
                                crypto_confirmed_at=timezone.now(),
                            )
                            order_item.pembelian_akun = pembelian_akun
                            order_item.save()
                            
                            # Reduce stock
                            order_item.akun.stock = max(0, order_item.akun.stock - order_item.quantity)
                            if order_item.akun.stock == 0:
                                order_item.akun.is_sold = True
                            order_item.akun.save()
                    except Exception as e:
                        print(f"Error creating pembelian for order_item {order_item.id}: {e}")
                        continue
                
                if cart_order.kupon:
                    cart_order.kupon.digunakan_oleh.add(cart_order.pembeli)
                
                # Send email notification
                try:
                    from .utils import decrypt_data
                    subject = f'Pesanan Cart [COMPLETED] - Kode: {cart_order.kode_transaksi}'
                    message = f"""Halo {cart_order.pembeli.username},

Pembayaran crypto Anda telah berhasil diverifikasi!

Kode Transaksi: {cart_order.kode_transaksi}
Transaction Hash: {tx_hash}
Confirmations: {confirmations}

Detail Akun yang Dibeli:
"""
                    for order_item in cart_order.order_items.filter(item_type='AKUN'):
                        if order_item.akun and order_item.pembelian_akun:
                            try:
                                email_dec = decrypt_data(order_item.akun.akun_email)
                                pass_dec = decrypt_data(order_item.akun.akun_password)
                                message += f"""
- {order_item.akun.nama_akun} ({order_item.akun.game})
  Email/Username: {email_dec}
  Password: {pass_dec}
"""
                            except Exception as e:
                                message += f"\n- {order_item.akun.nama_akun} ({order_item.akun.game})\n"
                    
                    message += "\nTerima kasih,\nTim MainAjaa"
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [cart_order.pembeli.email], fail_silently=False)
                except Exception as e:
                    print(f"Error sending email: {e}")
                
                return Response({
                    'success': 'Pembayaran berhasil diverifikasi!',
                    'status': 'COMPLETED',
                    'confirmations': confirmations,
                    'message': 'Pembayaran Anda telah dikonfirmasi. Detail akun telah dikirim ke email Anda.'
                }, status=status.HTTP_200_OK)
            else:
                # Manual verification needed
                return Response({
                    'success': 'Transaction hash berhasil disimpan.',
                    'status': 'PENDING',
                    'message': 'Pembayaran sedang dalam proses verifikasi. Anda akan menerima notifikasi setelah pembayaran dikonfirmasi.',
                    'verification_note': error_msg if error_msg else 'Menunggu konfirmasi blockchain'
                }, status=status.HTTP_200_OK)
                
        elif pembelian:
            pembelian.crypto_tx_hash = tx_hash
            pembelian.save()
            
            # Try to verify payment automatically
            from .crypto_payment import verify_crypto_payment
            is_verified, confirmations, error_msg = verify_crypto_payment(
                tx_hash,
                pembelian.crypto_currency,
                pembelian.crypto_amount,
                pembelian.crypto_address
            )
            
            if is_verified and confirmations >= 1:
                # Auto-verify if transaction is confirmed
                pembelian.status = 'COMPLETED'
                pembelian.crypto_confirmed_at = timezone.now()
                pembelian.save()
                
                # Reduce stock
                if pembelian.akun:
                    pembelian.akun.stock = max(0, pembelian.akun.stock - 1)
                    if pembelian.akun.stock == 0:
                        pembelian.akun.is_sold = True
                    pembelian.akun.save()
                
                if pembelian.kupon:
                    pembelian.kupon.digunakan_oleh.add(pembelian.pembeli)
                
                # Send email notification
                try:
                    from .utils import decrypt_data
                    subject = f'Pesanan [COMPLETED] - Kode: {pembelian.kode_transaksi}'
                    akun_email_dec = decrypt_data(pembelian.akun.akun_email)
                    akun_pass_dec = decrypt_data(pembelian.akun.akun_password)
                    message = f"""Halo {pembelian.pembeli.username},

Pembayaran crypto Anda telah berhasil diverifikasi!

Kode Transaksi: {pembelian.kode_transaksi}
Transaction Hash: {tx_hash}
Confirmations: {confirmations}

Detail Akun:
Email/Username: {akun_email_dec}
Password: {akun_pass_dec}

Harap segera ganti password dan amankan akun Anda.

Terima kasih,
Tim MainAjaa"""
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [pembelian.pembeli.email], fail_silently=False)
                except Exception as e:
                    print(f"Error sending email: {e}")
                
                return Response({
                    'success': 'Pembayaran berhasil diverifikasi!',
                    'status': 'COMPLETED',
                    'confirmations': confirmations,
                    'message': 'Pembayaran Anda telah dikonfirmasi. Detail akun telah dikirim ke email Anda.'
                }, status=status.HTTP_200_OK)
            else:
                # Manual verification needed
                return Response({
                    'success': 'Transaction hash berhasil disimpan.',
                    'status': 'PENDING',
                    'message': 'Pembayaran sedang dalam proses verifikasi. Anda akan menerima notifikasi setelah pembayaran dikonfirmasi.',
                    'verification_note': error_msg if error_msg else 'Menunggu konfirmasi blockchain'
                }, status=status.HTTP_200_OK)
    
    except (Pembelian.DoesNotExist, CartOrder.DoesNotExist):
        return Response({'error': 'Pesanan tidak ditemukan atau bukan milik Anda.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error verifying crypto payment: {e}")
        return Response({'error': f'Gagal memverifikasi pembayaran: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchase_detail(request, kode_transaksi):
    """
    Mengambil detail satu pesanan (Akun, TopUp, atau CartOrder)
    berdasarkan kode_transaksi dan memastikan itu milik user.
    """
    user = request.user
    
    try:
        if kode_transaksi.startswith('CART-'):
            # Ambil CartOrder
            cart_order = CartOrder.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
            
            # Prepare response dengan semua order items
            order_items_data = []
            for order_item in cart_order.order_items.all():
                item_data = {
                    'id': order_item.id,
                    'item_type': order_item.item_type,
                    'quantity': order_item.quantity,
                    'harga_saat_ditambahkan': float(order_item.harga_saat_ditambahkan),
                    'total_price': float(order_item.get_total_price()),
                }
                
                # Cart hanya support AKUN
                if order_item.item_type == 'AKUN' and order_item.akun:
                    item_data['akun'] = {
                        'id': order_item.akun.id,
                        'nama_akun': order_item.akun.nama_akun,
                        'game': order_item.akun.game,
                        'level': order_item.akun.level,
                    }
                    # Jika sudah completed, include email dan password yang sudah di-decrypt
                    if cart_order.status == 'COMPLETED':
                        try:
                            item_data['akun_email'] = decrypt_data(order_item.akun.akun_email)
                            item_data['akun_password'] = decrypt_data(order_item.akun.akun_password)
                        except Exception as e:
                            print(f"Error decrypting account data for order_item {order_item.id}: {e}")
                            item_data['akun_email'] = None
                            item_data['akun_password'] = None
                        
                        # Include pembelian reference jika ada
                        if order_item.pembelian_akun:
                            item_data['pembelian_kode_transaksi'] = order_item.pembelian_akun.kode_transaksi
                            item_data['pembelian_id'] = order_item.pembelian_akun.id
                    else:
                        item_data['akun_email'] = None
                        item_data['akun_password'] = None
                        item_data['pembelian_kode_transaksi'] = None
                
                order_items_data.append(item_data)
            
            response_data = {
                'tipe': 'CART',
                'kode_transaksi': cart_order.kode_transaksi,
                'status': cart_order.status,
                'harga_total': float(cart_order.harga_total),
                'dibuat_pada': cart_order.dibuat_pada.isoformat(),
                'kupon': cart_order.kupon.kode if cart_order.kupon else None,
                'order_items': order_items_data,
                'total_items': len(order_items_data),
                'midtrans_token': cart_order.midtrans_token,
                # Info untuk frontend
                'is_cart_order': True,
                'message': 'Cart order berisi multiple akun. Detail email dan password setiap akun tersedia di bawah.' if cart_order.status == 'COMPLETED' else 'Menunggu pembayaran. Email dan password akan tersedia setelah pembayaran berhasil.',
            }
            
            return Response(response_data)
            
        elif kode_transaksi.startswith('AKUN-'):
            # Ambil pembelian AKUN
            pembelian = Pembelian.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
            # Gunakan serializer detail yang bisa dekripsi
            serializer = PembelianDetailSerializer(pembelian)
            return Response(serializer.data)
            
        elif kode_transaksi.startswith('TOPUP-'):
            # Ambil pembelian TOP UP
            pembelian = TopUpPembelian.objects.get(kode_transaksi=kode_transaksi, pembeli=user)
            # Gunakan serializer TopUp yang sudah ada (cukup detail)
            serializer = TopUpPembelianSerializer(pembelian)
            return Response(serializer.data)
        
        else:
            return Response({'error': 'Format kode transaksi tidak valid.'}, status=status.HTTP_400_BAD_REQUEST)
            
    except (Pembelian.DoesNotExist, TopUpPembelian.DoesNotExist, CartOrder.DoesNotExist):
        return Response({'error': 'Pesanan tidak ditemukan atau bukan milik Anda.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error get_purchase_detail: {e}")
        import traceback
        traceback.print_exc()
        return Response({'error': 'Terjadi kesalahan internal.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    if akun.stock <= 0:
        return Response({'error': 'Maaf, stok akun ini sudah habis.'}, status=status.HTTP_400_BAD_REQUEST)
    if akun.is_sold:
        return Response({'error': 'Akun sudah terjual'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get payment method from request
    payment_method = data.get('payment_method', 'MIDTRANS')
    if payment_method not in ['MIDTRANS', 'CRYPTO_USDT', 'CRYPTO_ETH', 'CRYPTO_SOL']:
        payment_method = 'MIDTRANS'
        
    try:
        pembelian_obj, payment_token = Pembelian.create_pembelian(
            pembeli=user, akun=akun, kode_kupon_str=kode_kupon, payment_method=payment_method
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

        # payment_token bisa berupa midtrans_token atau None (untuk crypto)
        response_data = {
            'pembelian_id': pembelian_obj.id,
            'kode_transaksi': pembelian_obj.kode_transaksi,
        }
        
        if payment_method == 'MIDTRANS' and payment_token:
            response_data['midtrans_token'] = payment_token
        elif payment_method.startswith('CRYPTO_'):
            # Untuk crypto payment, kirim data wallet
            response_data['crypto_address'] = pembelian_obj.crypto_address
            response_data['crypto_amount'] = float(pembelian_obj.crypto_amount) if pembelian_obj.crypto_amount else None
            response_data['crypto_currency'] = pembelian_obj.crypto_currency
            response_data['harga_total'] = float(pembelian_obj.harga_total)
        
        return Response(response_data)
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
    Mengambil gabungan riwayat pembelian Akun, Top Up, dan CartOrder untuk user yang login,
    diurutkan berdasarkan tanggal terbaru.
    
    Untuk cart order:
    - Cart order muncul sebagai 1 item di history
    - Individual pembelian yang dibuat dari cart order juga muncul terpisah
    - User bisa melihat detail cart order untuk melihat semua akun dengan email/password
    """
    user = request.user

    # Get individual purchases (termasuk yang dibuat dari cart order)
    akun_history = Pembelian.objects.filter(pembeli=user)
    topup_history = TopUpPembelian.objects.filter(pembeli=user)
    akun_data = RiwayatAkunSerializer(akun_history, many=True).data
    topup_data = RiwayatTopUpSerializer(topup_history, many=True).data
    
    # Tambahkan flag untuk menandai apakah pembelian dari cart order
    for item in akun_data:
        # Check if this pembelian is from cart order
        pembelian_obj = akun_history.filter(id=item.get('id')).first()
        if pembelian_obj and hasattr(pembelian_obj, 'cart_order_item') and pembelian_obj.cart_order_item.exists():
            cart_order_item = pembelian_obj.cart_order_item.first()
            item['from_cart_order'] = cart_order_item.cart_order.kode_transaksi
            item['cart_order_kode'] = cart_order_item.cart_order.kode_transaksi
        else:
            item['from_cart_order'] = None
            item['cart_order_kode'] = None
    
    # Get cart orders (muncul sebagai 1 item untuk setiap cart order)
    cart_orders = CartOrder.objects.filter(pembeli=user).order_by('-dibuat_pada')
    cart_data = []
    for cart_order in cart_orders:
        # Count hanya akun (cart hanya support AKUN sekarang)
        akun_count = cart_order.order_items.filter(item_type='AKUN').count()
        cart_data.append({
            'id': cart_order.id,
            'kode_transaksi': cart_order.kode_transaksi,
            'tipe': 'CART',
            'nama_item': f'Cart Order ({akun_count} akun)',
            'total': float(cart_order.harga_total),
            'status': cart_order.status,
            'tanggal': cart_order.dibuat_pada.isoformat(),
            'midtrans_token': cart_order.midtrans_token,
            'item_count': akun_count,
            'is_cart_order': True,  # Flag untuk frontend
        })
    
    # Combine semua data
    combined_history = list(akun_data) + list(topup_data) + list(cart_data)
    
    # Sort by tanggal (dibuat_pada untuk akun, tanggal_pembelian untuk topup, dibuat_pada untuk cart)
    def get_sort_key(item):
        if item.get('tipe') == 'CART':
            return item.get('tanggal', '')
        elif item.get('tipe') == 'topup':
            return item.get('tanggal_pembelian', item.get('tanggal', ''))
        else:
            return item.get('tanggal', item.get('dibuat_pada', ''))
    
    combined_history.sort(key=get_sort_key, reverse=True)
    
    return Response(combined_history)

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def midtrans_webhook(request):
    """
    Endpoint untuk menerima notifikasi webhook dari Midtrans.
    Menangani AKUN, TOPUP, dan CART order.
    """
    try:
        # Midtrans mengirim data sebagai JSON dalam request.body
        import json
        if hasattr(request, 'body') and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = request.data
        else:
            data = request.data
            
        order_id = data.get('order_id')
        status_code = data.get('status_code')
        gross_amount = data.get('gross_amount')
        signature_key = data.get('signature_key')
        transaction_status = data.get('transaction_status')

        # 1. Verifikasi Signature Key (Keamanan) - skip jika tidak ada signature_key (untuk testing)
        if signature_key and status_code and gross_amount:
            expected_signature = _buat_signature_key(order_id, status_code, gross_amount)
            if signature_key != expected_signature:
                print(f"WEBHOOK GAGAL: Signature key tidak valid untuk order {order_id}")
                return Response({'status': 'error', 'message': 'Invalid signature'}, status=400)

        # 2. Tentukan model berdasarkan prefix order_id
        pembelian = None
        cart_order = None
        model_type = None

        if order_id.startswith('CART-'):
            # Handle Cart Order - multiple items dalam satu transaction
            try:
                cart_order = CartOrder.objects.get(kode_transaksi=order_id)
                model_type = 'CART'
            except CartOrder.DoesNotExist:
                print(f"WEBHOOK GAGAL: CartOrder {order_id} tidak ditemukan.")
                return Response({'status': 'error', 'message': 'Order not found'}, status=404)
        
        elif order_id.startswith('AKUN-'):
            try:
                pembelian = Pembelian.objects.get(kode_transaksi=order_id)
                model_type = 'AKUN'
            except Pembelian.DoesNotExist:
                pass
        
        elif order_id.startswith('TOPUP-'):
            try:
                pembelian = TopUpPembelian.objects.get(kode_transaksi=order_id)
                model_type = 'TOPUP'
            except TopUpPembelian.DoesNotExist:
                pass

        # 3. Handle jika order tidak ditemukan
        if not pembelian and not cart_order:
            print(f"WEBHOOK GAGAL: Order {order_id} tidak ditemukan di model manapun.")
            return Response({'status': 'error', 'message': 'Order not found'}, status=404)

        # 4. Update status di database
        if transaction_status == 'capture' or transaction_status == 'settlement':
            if model_type == 'CART':
                # Handle Cart Order
                if cart_order.status != 'COMPLETED':
                    cart_order.status = 'COMPLETED'
                    cart_order.save()
                    
                    # Create pembelian untuk setiap item dalam cart order (hanya AKUN)
                    for order_item in cart_order.order_items.all():
                        try:
                            # Cart hanya support AKUN
                            if order_item.item_type == 'AKUN' and order_item.akun:
                                # Create Pembelian untuk akun
                                pembelian_akun = Pembelian.objects.create(
                                    pembeli=cart_order.pembeli,
                                    akun=order_item.akun,
                                    harga_total=order_item.get_total_price(),
                                    harga_asli=order_item.harga_saat_ditambahkan,
                                    kupon=cart_order.kupon,
                                    status='COMPLETED'  # Langsung COMPLETED karena payment sudah success
                                )
                                order_item.pembelian_akun = pembelian_akun
                                order_item.save()
                                
                                # Reduce stock and mark as sold if stock is 0
                                order_item.akun.stock = max(0, order_item.akun.stock - order_item.quantity)
                                if order_item.akun.stock == 0:
                                    order_item.akun.is_sold = True
                                order_item.akun.save()
                                print(f"WEBHOOK: Akun {order_item.akun.id} stock dikurangi {order_item.quantity}, sisa stock: {order_item.akun.stock}")
                        
                        except Exception as e:
                            print(f"WEBHOOK ERROR: Gagal create pembelian untuk order_item {order_item.id}: {e}")
                            continue
                    
                    # Mark kupon as used
                    if cart_order.kupon:
                        cart_order.kupon.digunakan_oleh.add(cart_order.pembeli)
                    
                    # Send email notification
                    try:
                        # Dekripsi data akun untuk email (hanya AKUN, cart hanya support AKUN)
                        akun_details = []
                        for order_item in cart_order.order_items.filter(item_type='AKUN'):
                            if order_item.akun:
                                try:
                                    akun_email_dec = decrypt_data(order_item.akun.akun_email)
                                    akun_pass_dec = decrypt_data(order_item.akun.akun_password)
                                    akun_details.append({
                                        'nama': order_item.akun.nama_akun,
                                        'email': akun_email_dec,
                                        'password': akun_pass_dec
                                    })
                                except Exception as e:
                                    print(f"Error decrypting account {order_item.akun.id} for email: {e}")
                        
                        subject = f'Pesanan Cart LUNAS - Kode: {cart_order.kode_transaksi}'
                        message = f"""
Halo {cart_order.pembeli.username},

Pembayaran Anda untuk pesanan cart {cart_order.kode_transaksi} telah berhasil!

Total Pembayaran: Rp {cart_order.harga_total:,.0f}
Jumlah Akun: {len(akun_details)}

"""
                        if akun_details:
                            message += "Berikut adalah detail data akun yang Anda beli:\n"
                            message += "==========================================\n"
                            for idx, akun in enumerate(akun_details, 1):
                                message += f"\n[{idx}] Akun: {akun['nama']}\n"
                                message += f"    Email/Username: {akun['email']}\n"
                                message += f"    Password: {akun['password']}\n"
                                message += "==========================================\n"
                        
                        message += "\nData ini juga dapat diakses melalui halaman 'Riwayat Pesanan' di profil Anda.\n"
                        message += "Klik pada Cart Order untuk melihat detail semua akun.\n\n"
                        message += "Terima kasih telah berbelanja,\nTim MainAjaa"
                        
                        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [cart_order.pembeli.email], fail_silently=False)
                        print(f"WEBHOOK: Email konfirmasi cart order LUNAS dikirim ke {cart_order.pembeli.email}")
                    except Exception as e:
                        print(f"WEBHOOK ERROR: Gagal mengirim email untuk cart order: {e}")
                    
                    print(f"WEBHOOK SUKSES: Cart order {order_id} completed dan pembelian dibuat.")
            
            elif model_type == 'AKUN' and pembelian:
                # Handle single AKUN purchase
                if pembelian.status != 'COMPLETED':
                    pembelian.status = 'COMPLETED'
                    pembelian.save()
                    
                    if pembelian.akun:
                        # Reduce stock and mark as sold if stock is 0
                        pembelian.akun.stock = max(0, pembelian.akun.stock - 1)
                        if pembelian.akun.stock == 0:
                            pembelian.akun.is_sold = True
                        pembelian.akun.save()
                        print(f"WEBHOOK SUKSES: Akun {pembelian.akun.id} stock dikurangi 1, sisa stock: {pembelian.akun.stock}")
                    
                    # Send email (existing logic)
                    try:
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

Harap segera amankan akun Anda. Data ini juga dapat diakses melalui halaman 'Riwayat Pesanan' di profil Anda.

Terima kasih telah berbelanja,
Tim MainAjaa
                        """
                        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [pembelian.pembeli.email], fail_silently=False)
                        print(f"WEBHOOK: Email konfirmasi LUNAS dikirim ke {pembelian.pembeli.email}")
                    except Exception as e:
                        print(f"WEBHOOK ERROR: Gagal mengirim email: {e}")
                    
                    if pembelian.kupon:
                        pembelian.kupon.digunakan_oleh.add(pembelian.pembeli)
                    
                    print(f"WEBHOOK SUKSES: Status untuk {order_id} sudah COMPLETED.")
            
            elif model_type == 'TOPUP' and pembelian:
                # Handle single TOPUP purchase
                if pembelian.status != 'COMPLETED':
                    pembelian.status = 'COMPLETED'
                    pembelian.save()
                    
                    # Send email (existing logic)
                    try:
                        subject = f'Pesanan Top Up LUNAS - Kode: {pembelian.kode_transaksi}'
                        message = f"""
Halo {pembelian.pembeli.username},

Pembayaran Anda untuk pesanan Top Up {pembelian.kode_transaksi} ({pembelian.produk.nama_paket}) telah berhasil!

Top up Anda akan segera kami proses ke:
Game ID: {pembelian.game_user_id} {pembelian.game_zone_id or ''}

Terima kasih telah berbelanja,
Tim MainAjaa
                        """
                        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [pembelian.pembeli.email], fail_silently=False)
                        print(f"WEBHOOK: Email konfirmasi top up LUNAS dikirim ke {pembelian.pembeli.email}")
                    except Exception as e:
                        print(f"WEBHOOK ERROR: Gagal mengirim email: {e}")
                    
                    if pembelian.kupon:
                        pembelian.kupon.digunakan_oleh.add(pembelian.pembeli)
                    
                    print(f"WEBHOOK SUKSES: Status untuk {order_id} sudah COMPLETED.")

        elif transaction_status == 'cancel' or transaction_status == 'expire' or transaction_status == 'deny':
            if model_type == 'CART' and cart_order:
                if cart_order.status != 'CANCELED':
                    cart_order.status = 'CANCELED'
                    cart_order.save()
                    # Restore stock for all items in cart order
                    for order_item in cart_order.order_items.filter(item_type='AKUN'):
                        if order_item.akun:
                            order_item.akun.stock += order_item.quantity
                            order_item.akun.is_sold = False
                            order_item.akun.save()
                            print(f"WEBHOOK: Stock akun {order_item.akun.id} dikembalikan {order_item.quantity}, stock sekarang: {order_item.akun.stock}")
                print(f"WEBHOOK: Cart order {order_id} diupdate ke CANCELED.")
            elif pembelian:
                if pembelian.status != 'CANCELED':
                    pembelian.status = 'CANCELED'
                    pembelian.save()
                    # Revert akun status if AKUN (restore stock)
                    if model_type == 'AKUN' and pembelian.akun:
                        pembelian.akun.stock += 1  # Restore stock
                        pembelian.akun.is_sold = False
                        pembelian.akun.save()
                        print(f"WEBHOOK: Stock akun {pembelian.akun.id} dikembalikan, stock sekarang: {pembelian.akun.stock}")
                print(f"WEBHOOK: Status untuk {order_id} diupdate ke CANCELED.")

        # Kirim balasan 200 OK ke Midtrans
        return Response({'status': 'ok'}, status=200)

    except Exception as e:
        print(f"WEBHOOK CRASH: Terjadi error: {e}")
        import traceback
        traceback.print_exc()
        return Response({'status': 'error', 'message': str(e)}, status=500)

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

# Function removed - using the enhanced version below (line 1241)

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
    stock = request.data.get('stock', 1)  # Default stock = 1
    # --- TAMBAHKAN INI ---
    akun_email = request.data.get('akun_email')
    akun_password = request.data.get('akun_password')
    # --- Selesai ---

    gambar_cover = request.FILES.get('gambar')
    gambar_galeri = request.FILES.getlist('images[]')

    # Validasi (Tambahkan validasi kredensial)
    if not all([nama_akun, game, harga, gambar_cover, akun_email, akun_password]): # <-- Tambahkan akun_email & akun_password
        return Response({'error': 'Semua field bertanda * wajib diisi.'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validasi stock
    try:
        stock = int(stock)
        if stock < 0:
            return Response({'error': 'Stock tidak boleh negatif.'}, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({'error': 'Stock harus berupa angka.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # --- Enkripsi Kredensial ---
        encrypted_email = encrypt_data(akun_email)
        encrypted_password = encrypt_data(akun_password)
        if not encrypted_email or not encrypted_password:
             raise ValueError("Gagal mengenkripsi kredensial akun.")
        # --- Selesai Enkripsi ---

        # Buat objek AkunGaming utama (Tambahkan kredensial terenkripsi dan stock)
        akun = AkunGaming.objects.create(
            nama_akun=nama_akun,
            game=game,
            level=level if level else 1,
            deskripsi=deskripsi,
            harga=harga,
            gambar=gambar_cover,
            stock=stock,
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
        if 'stock' in request.data:
            try:
                stock = int(request.data.get('stock'))
                if stock >= 0:
                    akun.stock = stock
                    # Update is_sold jika stock habis
                    if stock == 0:
                        akun.is_sold = True
                    elif stock > 0 and akun.is_sold:
                        akun.is_sold = False
            except (ValueError, TypeError):
                pass  # Skip jika stock tidak valid
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

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_analytics_data(request):
    """
    Mengembalikan data analytics lengkap untuk dashboard.
    Menggunakan timezone-aware datetime untuk menghindari RuntimeWarning.
    """
    from django.utils import timezone
    from datetime import timedelta, datetime
    from collections import defaultdict
    
    # Time ranges - menggunakan timezone-aware datetime
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    
    # Convert dates to timezone-aware datetimes for filtering
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    yesterday_start = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
    yesterday_end = timezone.make_aware(datetime.combine(yesterday, datetime.max.time()))
    this_month_start_dt = timezone.make_aware(datetime.combine(this_month_start, datetime.min.time()))
    last_month_start_dt = timezone.make_aware(datetime.combine(last_month_start, datetime.min.time()))
    last_month_end_dt = timezone.make_aware(datetime.combine(last_month_end, datetime.max.time()))
    
    # Basic Stats
    total_users = User.objects.count()
    total_products = AkunGaming.objects.count() + TopUpProduct.objects.count()
    total_orders = Pembelian.objects.count() + TopUpPembelian.objects.count()
    
    # Revenue Stats - menggunakan timezone-aware datetime
    revenue_today = (
        Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=today_start).aggregate(total=Sum('harga_total'))['total'] or 0
    ) + (
        TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=today_start).aggregate(total=Sum('harga_pembelian'))['total'] or 0
    )
    
    revenue_yesterday = (
        Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=yesterday_start, dibuat_pada__lte=yesterday_end).aggregate(total=Sum('harga_total'))['total'] or 0
    ) + (
        TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=yesterday_start, tanggal_pembelian__lte=yesterday_end).aggregate(total=Sum('harga_pembelian'))['total'] or 0
    )
    
    revenue_last_7_days = (
        Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=last_7_days).aggregate(total=Sum('harga_total'))['total'] or 0
    ) + (
        TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=last_7_days).aggregate(total=Sum('harga_pembelian'))['total'] or 0
    )
    
    revenue_last_30_days = (
        Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=last_30_days).aggregate(total=Sum('harga_total'))['total'] or 0
    ) + (
        TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=last_30_days).aggregate(total=Sum('harga_pembelian'))['total'] or 0
    )
    
    revenue_this_month = (
        Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=this_month_start_dt).aggregate(total=Sum('harga_total'))['total'] or 0
    ) + (
        TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=this_month_start_dt).aggregate(total=Sum('harga_pembelian'))['total'] or 0
    )
    
    revenue_last_month = (
        Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=last_month_start_dt, dibuat_pada__lte=last_month_end_dt).aggregate(total=Sum('harga_total'))['total'] or 0
    ) + (
        TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=last_month_start_dt, tanggal_pembelian__lte=last_month_end_dt).aggregate(total=Sum('harga_pembelian'))['total'] or 0
    )
    
    # Order Stats
    orders_today = (
        Pembelian.objects.filter(dibuat_pada__gte=today_start).count() +
        TopUpPembelian.objects.filter(tanggal_pembelian__gte=today_start).count()
    )
    
    orders_last_7_days = (
        Pembelian.objects.filter(dibuat_pada__gte=last_7_days).count() +
        TopUpPembelian.objects.filter(tanggal_pembelian__gte=last_7_days).count()
    )
    
    # Sales by Game
    sales_by_game = defaultdict(lambda: {'count': 0, 'revenue': 0})
    
    # Account sales by game
    account_sales = Pembelian.objects.filter(status='COMPLETED').values('akun__game').annotate(
        count=Count('id'),
        revenue=Sum('harga_total')
    )
    for sale in account_sales:
        game = sale['akun__game'] or 'Unknown'
        sales_by_game[game]['count'] += sale['count']
        sales_by_game[game]['revenue'] += float(sale['revenue'] or 0)
    
    # Topup sales by game
    topup_sales = TopUpPembelian.objects.filter(status='COMPLETED').values('produk__game').annotate(
        count=Count('id'),
        revenue=Sum('harga_pembelian')
    )
    for sale in topup_sales:
        game = sale['produk__game'] or 'Unknown'
        sales_by_game[game]['count'] += sale['count']
        sales_by_game[game]['revenue'] += float(sale['revenue'] or 0)
    
    sales_by_game_list = [
        {'game': game, 'count': data['count'], 'revenue': data['revenue']}
        for game, data in sorted(sales_by_game.items(), key=lambda x: x[1]['revenue'], reverse=True)
    ]
    
    # Top Selling Products (Accounts)
    top_accounts = Pembelian.objects.filter(status='COMPLETED', akun__isnull=False).values(
        'akun__nama_akun', 'akun__game', 'akun__harga'
    ).annotate(
        sales_count=Count('id')
    ).order_by('-sales_count')[:5]
    
    # Top Selling TopUp Products
    top_topups = TopUpPembelian.objects.filter(status='COMPLETED').values(
        'produk__nama_paket', 'produk__game', 'produk__harga'
    ).annotate(
        sales_count=Count('id')
    ).order_by('-sales_count')[:5]
    
    # Recent Orders (last 10)
    recent_account_orders = Pembelian.objects.select_related('akun', 'pembeli').order_by('-dibuat_pada')[:5]
    recent_topup_orders = TopUpPembelian.objects.select_related('produk', 'pembeli').order_by('-tanggal_pembelian')[:5]
    
    recent_orders = []
    for order in recent_account_orders:
        recent_orders.append({
            'id': order.id,
            'type': 'AKUN',
            'item_name': order.akun.nama_akun if order.akun else 'N/A',
            'customer': order.pembeli.username if order.pembeli else 'N/A',
            'amount': float(order.harga_total),
            'status': order.status,
            'date': order.dibuat_pada.isoformat(),
        })
    
    for order in recent_topup_orders:
        recent_orders.append({
            'id': order.id,
            'type': 'TOPUP',
            'item_name': order.produk.nama_paket if order.produk else 'N/A',
            'customer': order.pembeli.username if order.pembeli else 'N/A',
            'amount': float(order.harga_pembelian),
            'status': order.status,
            'date': order.tanggal_pembelian.isoformat(),
        })
    
    recent_orders.sort(key=lambda x: x['date'], reverse=True)
    recent_orders = recent_orders[:10]
    
    # Daily Revenue (last 7 days) - menggunakan timezone-aware
    daily_revenue = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        date_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        date_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
        day_revenue = (
            Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=date_start, dibuat_pada__lte=date_end).aggregate(total=Sum('harga_total'))['total'] or 0
        ) + (
            TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=date_start, tanggal_pembelian__lte=date_end).aggregate(total=Sum('harga_pembelian'))['total'] or 0
        )
        daily_revenue.append({
            'date': date.isoformat(),
            'revenue': float(day_revenue),
        })
    
    # Conversion Rate (simplified)
    total_views = AkunGaming.objects.count() * 10  # Estimated
    total_sales = Pembelian.objects.filter(status='COMPLETED').count() + TopUpPembelian.objects.filter(status='COMPLETED').count()
    conversion_rate = (total_sales / total_views * 100) if total_views > 0 else 0
    
    # Average Order Value
    avg_order_value = revenue_last_30_days / orders_last_7_days if orders_last_7_days > 0 else 0
    
    # Hourly Revenue (today)
    hourly_revenue = []
    for hour in range(24):
        hour_start = timezone.make_aware(datetime.combine(today, datetime.min.time().replace(hour=hour)))
        hour_end = timezone.make_aware(datetime.combine(today, datetime.min.time().replace(hour=hour+1))) if hour < 23 else timezone.make_aware(datetime.combine(today, datetime.max.time()))
        hour_rev = (
            Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=hour_start, dibuat_pada__lt=hour_end).aggregate(total=Sum('harga_total'))['total'] or 0
        ) + (
            TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=hour_start, tanggal_pembelian__lt=hour_end).aggregate(total=Sum('harga_pembelian'))['total'] or 0
        )
        hourly_revenue.append({
            'hour': hour,
            'revenue': float(hour_rev),
        })
    
    # Weekly Revenue (last 4 weeks)
    weekly_revenue = []
    for week in range(4):
        week_start = today - timedelta(days=(week+1)*7)
        week_end = today - timedelta(days=week*7)
        week_start_dt = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
        week_end_dt = timezone.make_aware(datetime.combine(week_end, datetime.max.time()))
        week_rev = (
            Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=week_start_dt, dibuat_pada__lte=week_end_dt).aggregate(total=Sum('harga_total'))['total'] or 0
        ) + (
            TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=week_start_dt, tanggal_pembelian__lte=week_end_dt).aggregate(total=Sum('harga_pembelian'))['total'] or 0
        )
        weekly_revenue.append({
            'week': f'Week {4-week}',
            'date': week_start.isoformat(),
            'revenue': float(week_rev),
        })
    
    # Monthly Revenue (last 6 months)
    monthly_revenue = []
    for month in range(6):
        month_date = today.replace(day=1) - timedelta(days=month*30)
        month_start = month_date.replace(day=1)
        if month == 0:
            month_end = today
        else:
            next_month = month_start + timedelta(days=32)
            month_end = (next_month.replace(day=1) - timedelta(days=1))
        month_start_dt = timezone.make_aware(datetime.combine(month_start, datetime.min.time()))
        month_end_dt = timezone.make_aware(datetime.combine(month_end, datetime.max.time()))
        month_rev = (
            Pembelian.objects.filter(status='COMPLETED', dibuat_pada__gte=month_start_dt, dibuat_pada__lte=month_end_dt).aggregate(total=Sum('harga_total'))['total'] or 0
        ) + (
            TopUpPembelian.objects.filter(status='COMPLETED', tanggal_pembelian__gte=month_start_dt, tanggal_pembelian__lte=month_end_dt).aggregate(total=Sum('harga_pembelian'))['total'] or 0
        )
        monthly_revenue.append({
            'month': month_start.strftime('%b %Y'),
            'date': month_start.isoformat(),
            'revenue': float(month_rev),
        })
    monthly_revenue.reverse()
    
    # Order Status Breakdown
    order_status_breakdown = {
        'COMPLETED': Pembelian.objects.filter(status='COMPLETED').count() + TopUpPembelian.objects.filter(status='COMPLETED').count(),
        'PENDING': Pembelian.objects.filter(status='PENDING').count() + TopUpPembelian.objects.filter(status='PENDING').count(),
        'CANCELED': Pembelian.objects.filter(status='CANCELED').count() + TopUpPembelian.objects.filter(status='CANCELED').count(),
    }
    
    # Revenue by Product Type
    revenue_by_type = {
        'accounts': float(Pembelian.objects.filter(status='COMPLETED').aggregate(total=Sum('harga_total'))['total'] or 0),
        'topups': float(TopUpPembelian.objects.filter(status='COMPLETED').aggregate(total=Sum('harga_pembelian'))['total'] or 0),
    }
    
    # User Behavior (New vs Returning)
    from django.db.models import Q
    users_with_orders = User.objects.filter(
        Q(pembelian__isnull=False) | Q(topuppembelian__isnull=False)
    ).distinct()
    new_users_last_30 = User.objects.filter(date_joined__gte=last_30_days).count()
    returning_users = max(0, users_with_orders.count() - new_users_last_30)
    
    # Conversion Funnel Data
    total_products_viewed = AkunGaming.objects.count() + TopUpProduct.objects.count()
    products_in_cart = 0  # Estimated - bisa ditambahkan jika ada cart feature
    orders_created = total_orders
    orders_completed = order_status_breakdown['COMPLETED']
    
    conversion_funnel = {
        'products_viewed': total_products_viewed,
        'products_in_cart': products_in_cart,
        'orders_created': orders_created,
        'orders_completed': orders_completed,
    }
    
    return Response({
        'summary': {
            'total_users': total_users,
            'total_products': total_products,
            'total_orders': total_orders,
            'conversion_rate': round(conversion_rate, 2),
            'avg_order_value': round(avg_order_value, 2),
        },
        'revenue': {
            'today': float(revenue_today),
            'yesterday': float(revenue_yesterday),
            'last_7_days': float(revenue_last_7_days),
            'last_30_days': float(revenue_last_30_days),
            'this_month': float(revenue_this_month),
            'last_month': float(revenue_last_month),
            'daily': daily_revenue,
            'hourly': hourly_revenue,
            'weekly': weekly_revenue,
            'monthly': monthly_revenue,
        },
        'orders': {
            'today': orders_today,
            'last_7_days': orders_last_7_days,
            'status_breakdown': order_status_breakdown,
        },
        'sales_by_game': sales_by_game_list,
        'revenue_by_type': revenue_by_type,
        'top_products': {
            'accounts': list(top_accounts),
            'topups': list(top_topups),
        },
        'recent_orders': recent_orders,
        'user_behavior': {
            'new_users_last_30': new_users_last_30,
            'returning_users': returning_users,
            'total_active_users': users_with_orders.count(),
        },
        'conversion_funnel': conversion_funnel,
    }, status=status.HTTP_200_OK)

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

# ===================================================================
# CART VIEWS
# ===================================================================

def get_or_create_cart(user):
    """Helper function untuk get or create cart untuk user"""
    cart, created = Cart.objects.get_or_create(user=user)
    return cart

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart(request):
    """Mengambil cart user (auto create jika belum ada)"""
    try:
        cart = get_or_create_cart(request.user)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def add_to_cart(request):
    """
    Menambahkan item AKUN ke cart.
    Cart hanya support AKUN, tidak support TOPUP karena top-up memerlukan input ID dan server.
    """
    user = request.user
    data = request.data
    item_type = data.get('item_type', 'AKUN')  # Default AKUN
    
    # Cart hanya support AKUN
    if item_type != 'AKUN':
        return Response({
            'error': 'Cart hanya mendukung akun gaming. Untuk top-up, silakan lakukan pembelian langsung.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        cart = get_or_create_cart(user)
        
        akun_id = data.get('akun_id')
        quantity = int(data.get('quantity', 1))
        
        if not akun_id:
            return Response({'error': 'akun_id diperlukan'}, status=status.HTTP_400_BAD_REQUEST)
        
        akun = get_object_or_404(AkunGaming, pk=akun_id)
        
        if akun.stock <= 0:
            return Response({'error': 'Maaf, stok akun ini sudah habis.'}, status=status.HTTP_400_BAD_REQUEST)
        if akun.is_sold:
            return Response({'error': 'Akun ini sudah terjual'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if item already exists in cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            item_type='AKUN',
            akun=akun,
            defaults={
                'quantity': quantity,
                'harga_saat_ditambahkan': akun.harga
            }
        )
        
        if not created:
            # Update quantity if item already exists
            cart_item.quantity += quantity
            cart_item.save()
        
        serializer = CartItemSerializer(cart_item, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_cart_item(request, item_id):
    """Update quantity cart item"""
    try:
        cart = get_or_create_cart(request.user)
        cart_item = get_object_or_404(CartItem, pk=item_id, cart=cart)
        
        quantity = request.data.get('quantity')
        if quantity is not None:
            quantity = int(quantity)
            if quantity <= 0:
                return Response({'error': 'Quantity harus lebih dari 0'}, status=status.HTTP_400_BAD_REQUEST)
            cart_item.quantity = quantity
            cart_item.save()
        
        serializer = CartItemSerializer(cart_item, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_cart(request, item_id):
    """Menghapus item dari cart"""
    try:
        cart = get_or_create_cart(request.user)
        cart_item = get_object_or_404(CartItem, pk=item_id, cart=cart)
        cart_item.delete()
        return Response({'success': 'Item berhasil dihapus dari cart'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_cart(request):
    """Menghapus semua item dari cart"""
    try:
        cart = get_or_create_cart(request.user)
        cart.items.all().delete()
        return Response({'success': 'Cart berhasil dikosongkan'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def checkout_from_cart(request):
    """
    Checkout dari cart - membuat satu CartOrder dengan semua item di cart.
    Semua item akan digabungkan dalam satu Midtrans transaction.
    """
    user = request.user
    data = request.data
    kode_kupon = data.get('kode_kupon', None)
    payment_method = data.get('payment_method', 'MIDTRANS')
    
    # Validate payment method
    if payment_method not in ['MIDTRANS', 'CRYPTO_USDT', 'CRYPTO_ETH', 'CRYPTO_SOL']:
        payment_method = 'MIDTRANS'
    
    try:
        cart = get_or_create_cart(user)
        cart_items = cart.items.all()
        
        if not cart_items.exists():
            return Response({'error': 'Cart kosong'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validasi semua items
        valid_items = []
        total_harga = Decimal('0')
        kupon_obj = None
        
        # Validasi kupon jika ada
        if kode_kupon:
            try:
                kupon_obj = Kupon.objects.get(kode__iexact=kode_kupon, aktif=True)
                if kupon_obj.digunakan_oleh.filter(id=user.id).exists():
                    return Response({'error': 'Kupon ini sudah pernah Anda gunakan.'}, status=status.HTTP_400_BAD_REQUEST)
            except Kupon.DoesNotExist:
                return Response({'error': 'Kupon tidak valid.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate total dan validate items (hanya AKUN)
        for item in cart_items:
            # Cart hanya support AKUN
            if item.item_type != 'AKUN':
                continue  # Skip non-AKUN items (shouldn't happen, but just in case)
            
            if not item.akun or item.akun.stock <= 0 or item.akun.is_sold:
                continue  # Skip jika akun tidak tersedia atau sudah terjual
            
            item_total = item.get_total_price()
            total_harga += item_total
            valid_items.append(item)
        
        if not valid_items:
            return Response({'error': 'Tidak ada item valid untuk checkout'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Apply kupon discount jika ada
        harga_asli = total_harga
        harga_final = total_harga
        if kupon_obj:
            diskon = (harga_asli * Decimal(kupon_obj.diskon_persen / 100))
            harga_final = harga_asli - diskon
        
        # Create CartOrder
        cart_order = CartOrder.objects.create(
            pembeli=user,
            harga_total=harga_final,
            kupon=kupon_obj,
            status='PENDING',
            payment_method=payment_method
        )
        
        # Create CartOrderItem untuk setiap item (hanya AKUN)
        item_details = []
        for item in valid_items:
            cart_order_item = CartOrderItem.objects.create(
                cart_order=cart_order,
                item_type='AKUN',
                akun=item.akun,
                quantity=item.quantity,
                harga_saat_ditambahkan=item.harga_saat_ditambahkan
            )
            
            # Prepare item details untuk Midtrans (jika menggunakan Midtrans)
            if payment_method == 'MIDTRANS':
                item_details.append({
                    'id': str(item.akun.id),
                    'price': int(item.harga_saat_ditambahkan),
                    'quantity': item.quantity,
                    'name': item.akun.nama_akun
                })
        
        # Handle payment based on payment method
        if payment_method == 'MIDTRANS':
            # Create Midtrans transaction dengan semua items
            try:
                snap = midtransclient.Snap(
                    is_production=settings.MIDTRANS_IS_PRODUCTION,
                    server_key=settings.MIDTRANS_SERVER_KEY,
                    client_key=settings.MIDTRANS_CLIENT_KEY
                )
                
                transaction_details = {
                    'order_id': str(cart_order.kode_transaksi),
                    'gross_amount': int(harga_final)
                }
                
                # Include item details untuk transparency
                transaction_data = {
                    'transaction_details': transaction_details,
                    'item_details': item_details
                }
                
                transaction = snap.create_transaction(transaction_data)
                midtrans_token = transaction['token']
                cart_order.midtrans_token = midtrans_token
                cart_order.save()
                
                payment_token = midtrans_token
            except Exception as e:
                # Rollback: delete cart_order jika Midtrans gagal
                cart_order.delete()
                print(f"Error creating Midtrans transaction: {e}")
                return Response({'error': f'Gagal membuat token pembayaran Midtrans: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Crypto payment
            from .crypto_payment import calculate_crypto_amount, get_crypto_wallet_address
            crypto_code = payment_method.replace('CRYPTO_', '')
            crypto_amount, crypto_price, idr_rate = calculate_crypto_amount(cart_order.harga_total, crypto_code)
            wallet_address = get_crypto_wallet_address(crypto_code)
            
            if not crypto_amount or not wallet_address:
                cart_order.delete()
                return Response({'error': f'Gagal membuat pembayaran crypto untuk {crypto_code}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            cart_order.crypto_address = wallet_address
            cart_order.crypto_amount = crypto_amount
            cart_order.crypto_currency = crypto_code
            cart_order.save()
            payment_token = None
        
        # Clear cart setelah order berhasil dibuat
        cart.items.all().delete()
        
        # Send email notification
        try:
            subject = f'Pesanan Cart [PENDING] - Kode: {cart_order.kode_transaksi}'
            message = f"""
Halo {user.username},

Pesanan Anda dengan {len(valid_items)} item telah berhasil dibuat dengan kode transaksi:
{cart_order.kode_transaksi}

Total Tagihan: Rp {cart_order.harga_total:,.0f}
Metode Pembayaran: {cart_order.get_payment_method_display()}

Pesanan ini sekarang menunggu pembayaran Anda.
Anda dapat melihat status pesanan dan melanjutkan pembayaran kapan saja melalui halaman Profil Anda.

Terima kasih,
Tim MainAjaa
            """
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            print(f"Email konfirmasi cart order (pending) dikirim ke {user.email} for order {cart_order.kode_transaksi}")
        except Exception as e:
            print(f"ERROR: Gagal mengirim email konfirmasi cart order: {e}")
        
        response_data = {
            'success': 'Checkout berhasil',
            'cart_order_id': cart_order.id,
            'kode_transaksi': cart_order.kode_transaksi,
            'total_items': len(valid_items),
            'total_price': float(harga_final),
            'payment_method': cart_order.payment_method,
        }
        
        if payment_method == 'MIDTRANS':
            response_data['midtrans_token'] = payment_token
        else:
            response_data['crypto_address'] = cart_order.crypto_address
            response_data['crypto_amount'] = float(cart_order.crypto_amount) if cart_order.crypto_amount else None
            response_data['crypto_currency'] = cart_order.crypto_currency
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        print(f"Error in checkout_from_cart: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart_count(request):
    """Mengambil jumlah item di cart (untuk badge di navbar)"""
    try:
        cart = get_or_create_cart(request.user)
        count = cart.get_item_count()
        return Response({'count': count}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'count': 0, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
