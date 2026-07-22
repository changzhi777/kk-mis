import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../api/auth_api.dart';

/// 认证状态（provider ChangeNotifier）。
///
/// 登录态 + token 持久化（shared_preferences）+ 角色判断（GET /dealer/balance
/// 200=经销商 / 403=消费者，复用 v2 API 不改后端 schema）。
class AuthStore extends ChangeNotifier {
  String? _token;
  bool _isDealer = false;
  bool _loading = true;
  String? _error;

  String? get token => _token;
  bool get isLoggedIn => _token != null;
  bool get isDealer => _isDealer;
  bool get loading => _loading;
  String? get error => _error;

  /// 启动调用：读持久化 token + 探测角色。
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('token');
    if (_token != null) {
      ApiClient.instance.setToken(_token!);
      await _checkRole();
    }
    _loading = false;
    notifyListeners();
  }

  Future<bool> login(String username, String password) async {
    _error = null;
    try {
      final data = await AuthApi.login(username, password);
      _token = data['access_token'] as String;
      ApiClient.instance.setToken(_token!);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('token', _token!);
      await _checkRole();
      notifyListeners();
      return true;
    } catch (e) {
      _error = '登录失败：$e';
      notifyListeners();
      return false;
    }
  }

  /// 探测角色：经销商余额端点 200=经销商，403/异常=消费者。
  Future<void> _checkRole() async {
    try {
      final r = await ApiClient.instance.v2.get('/dealer/balance');
      _isDealer = r.statusCode == 200;
    } catch (_) {
      _isDealer = false;
    }
  }

  Future<void> logout() async {
    _token = null;
    _isDealer = false;
    _error = null;
    ApiClient.instance.clearToken();
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('token');
    notifyListeners();
  }
}
