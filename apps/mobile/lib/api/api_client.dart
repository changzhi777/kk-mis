import 'package:dio/dio.dart';

import 'api_config.dart';

/// V2.0 APP HTTP 客户端（dio 单例 + JWT 拦截器）。
///
/// 登录后 setToken，所有请求自动带 Authorization: Bearer {token}。
/// v2 接经销商域，v1 接 admin/CMS（登录、产品）。
///
/// TODO M4.2: shared_preferences 持久化 token（启动自动登录）。
class ApiClient {
  static final ApiClient instance = ApiClient._internal();

  final Dio v2 = Dio(BaseOptions(
    baseUrl: ApiConfig.v2Url,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 15),
    headers: {'Content-Type': 'application/json'},
  ));

  final Dio v1 = Dio(BaseOptions(
    baseUrl: ApiConfig.v1Url,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 15),
    headers: {'Content-Type': 'application/json'},
  ));

  String? _token;

  ApiClient._internal() {
    for (final d in [v2, v1]) {
      d.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) {
            if (_token != null) {
              options.headers['Authorization'] = 'Bearer $_token';
            }
            handler.next(options);
          },
        ),
      );
    }
  }

  /// 登录成功后注入 token（自动带 header）。
  void setToken(String token) {
    _token = token;
  }

  void clearToken() {
    _token = null;
  }

  String? get token => _token;
  bool get isLoggedIn => _token != null;
}
