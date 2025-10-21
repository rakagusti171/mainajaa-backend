# backend/api/urls.py

from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # === Autentikasi & User ===
    path('token/', views.MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', views.registerUser, name='register'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),

    # === Akun Gaming (Publik) ===
    path('accounts/', views.akun_gaming_list, name='akun_list'),
    path('accounts/<int:pk>/', views.akun_gaming_detail, name='akun_detail'),
    path('accounts/<int:pk>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('accounts/<int:pk>/similar/', views.get_similar_accounts, name='similar_accounts'),
    path('accounts/favorit/', views.get_favorite_accounts, name='get_favorite_accounts'),
    path('pembelian/history/', views.get_pembelian_history, name='pembelian_history'),

    # === Top Up (Publik) ===
    path('topup-products/', views.TopUpProductList.as_view(), name='topup_list'),
    path('topup-products/<int:pk>/', views.TopUpProductDetail.as_view(), name='topup_detail'),
    path('check-game-id/', views.check_game_id_api, name='check_game_id'), 

    # === Kupon (User) ===
    path('validate-coupon-akun/', views.validate_coupon_api, name='validate_coupon_akun'),
    path('validate-coupon-topup/', views.validate_topup_coupon_api, name='validate_coupon_topup'), 

    # === Pembelian & Riwayat (User) ===
    path('pembelian/create-akun/', views.create_pembelian, name='create_pembelian_akun'),
    path('pembelian/create-topup/', views.create_topup_pembelian, name='create_pembelian_topup'),
    path('pembelian/history/', views.get_pembelian_history, name='pembelian_history'),
    path('pembelian/detail/<str:kode_transaksi>/', views.get_purchase_detail, name='purchase_detail'),
    path('pembelian/review/<int:purchase_id>/', views.submit_review, name='submit_review'),
    path('reviews/<str:game_name>/', views.get_reviews_by_game, name='game_reviews'),

    # === Webhook Midtrans ===
    path('webhook/midtrans/', views.midtrans_webhook, name='midtrans_webhook'),

    # === Dashboard Admin ===
    path('admin/all-orders/', views.admin_get_all_orders, name='admin_all_orders'),
    path('admin/dashboard-stats/', views.get_dashboard_stats, name='admin_dashboard_stats'),
    path('admin/all-products/', views.admin_get_all_products, name='admin_all_products'),
    path('admin/product/delete/', views.admin_delete_product, name='admin_delete_product'),
    path('admin/akun/create/', views.admin_create_akun, name='admin_create_akun'),
    path('admin/akun/<int:pk>/detail/', views.admin_get_akun_detail, name='admin_get_akun_detail'),
    path('admin/akun/<int:pk>/update/', views.admin_update_akun, name='admin_update_akun'),
    path('admin/topup/create/', views.admin_create_topup, name='admin_create_topup'),
    path('admin/topup/<int:pk>/detail/', views.admin_get_topup_detail, name='admin_get_topup_detail'),
    path('admin/topup/<int:pk>/update/', views.admin_update_topup, name='admin_update_topup'),
    path('admin/all-coupons/', views.admin_get_all_coupons, name='admin_all_coupons'),
    path('admin/coupon/create/', views.admin_create_coupon, name='admin_create_coupon'),
    path('admin/coupon/<int:pk>/toggle-active/', views.admin_toggle_coupon_active, name='admin_toggle_coupon_active'),
]