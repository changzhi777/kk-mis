import 'package:flutter_test/flutter_test.dart';
import 'package:dhts_app/api/api_client.dart';
import 'package:dhts_app/stores/auth_store.dart';

/// M4.5 单元测试（纯状态逻辑，不依赖 network mock）。
///
/// widget/集成测试（登录/激活流端到端）待 dio MockAdapter + shared_preferences
/// mock 基建完善后补；后端 51 测试已覆盖业务逻辑，APP 侧重状态契约。
void main() {
  group('ApiClient', () {
    test('token 状态：set/clear/isLoggedIn', () {
      ApiClient.instance.clearToken();
      expect(ApiClient.instance.isLoggedIn, false);
      expect(ApiClient.instance.token, isNull);

      ApiClient.instance.setToken('abc123');
      expect(ApiClient.instance.isLoggedIn, true);
      expect(ApiClient.instance.token, 'abc123');

      ApiClient.instance.clearToken();
      expect(ApiClient.instance.isLoggedIn, false);
      expect(ApiClient.instance.token, isNull);
    });

    test('v2/v1 baseUrl 配置', () {
      expect(ApiClient.instance.v2.options.baseUrl, contains('/admin/api/v2'));
      expect(ApiClient.instance.v1.options.baseUrl, contains('/admin/api/v1'));
    });
  });

  group('AuthStore', () {
    test('初始状态未登录/非经销商/无错误', () {
      final store = AuthStore();
      expect(store.isLoggedIn, false);
      expect(store.isDealer, false);
      expect(store.error, isNull);
    });
  });
}
