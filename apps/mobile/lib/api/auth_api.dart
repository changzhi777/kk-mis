import 'api_client.dart';

/// 认证 API（v1 admin auth）
class AuthApi {
  /// 登录：POST /admin/api/v1/auth/login → {access_token, refresh_token, user}
  static Future<Map<String, dynamic>> login(
    String username,
    String password,
  ) async {
    final r = await ApiClient.instance.v1.post(
      '/auth/login',
      data: {'username': username, 'password': password},
    );
    return (r.data as Map<String, dynamic>).cast<String, dynamic>();
  }
}
