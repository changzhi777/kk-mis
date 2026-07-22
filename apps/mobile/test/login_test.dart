import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dhts_app/api/api_client.dart';
import 'package:dhts_app/stores/auth_store.dart';

/// M4.5 端到端测试：dio MockAdapter + shared_preferences mock。
///
/// 覆盖 AuthStore login/init/logout + 角色探测（balance 200=dealer/403=customer），
/// 不依赖真后端。
class _MockAdapter implements HttpClientAdapter {
  final int statusCode;
  final Map<String, dynamic> body;
  _MockAdapter(this.body, {this.statusCode = 200});

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString(
      jsonEncode(body),
      statusCode,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    ApiClient.instance.clearToken();
  });

  test('login 成功 + 角色探测 customer（balance 403）', () async {
    ApiClient.instance.v1.httpClientAdapter = _MockAdapter({
      'access_token': 'tok123',
      'user': {'id': 1},
    });
    ApiClient.instance.v2.httpClientAdapter = _MockAdapter(
      {'detail': 'not dealer'},
      statusCode: 403,
    );

    final store = AuthStore();
    final ok = await store.login('user', 'pass');

    expect(ok, true);
    expect(store.isLoggedIn, true);
    expect(store.token, 'tok123');
    expect(store.isDealer, false); // balance 403 → 消费者
  });

  test('login 成功 + 角色探测 dealer（balance 200）', () async {
    ApiClient.instance.v1.httpClientAdapter = _MockAdapter({
      'access_token': 'tok',
      'user': {'id': 2},
    });
    ApiClient.instance.v2.httpClientAdapter = _MockAdapter({
      'balance': '0',
      'frozen': '0',
      'total_recharged': '0',
      'total_consumed': '0',
    });

    final store = AuthStore();
    final ok = await store.login('dealer', 'pass');

    expect(ok, true);
    expect(store.isDealer, true); // balance 200 → 经销商
  });

  test('login 失败（v1 401）→ error + 未登录', () async {
    ApiClient.instance.v1.httpClientAdapter = _MockAdapter(
      {'detail': 'bad credentials'},
      statusCode: 401,
    );

    final store = AuthStore();
    final ok = await store.login('x', 'y');

    expect(ok, false);
    expect(store.isLoggedIn, false);
    expect(store.error, isNotNull);
  });

  test('init 加载持久化 token', () async {
    SharedPreferences.setMockInitialValues({'token': 'persisted'});
    ApiClient.instance.v2.httpClientAdapter = _MockAdapter(
      {'detail': 'x'},
      statusCode: 403,
    );

    final store = AuthStore();
    await store.init();

    expect(store.loading, false);
    expect(store.isLoggedIn, true);
    expect(store.token, 'persisted');
    expect(store.isDealer, false);
  });

  test('logout 清空 token + 持久化删除', () async {
    SharedPreferences.setMockInitialValues({'token': 'x'});
    ApiClient.instance.v2.httpClientAdapter = _MockAdapter(
      {'detail': 'x'},
      statusCode: 403,
    );

    final store = AuthStore();
    await store.init();
    expect(store.isLoggedIn, true);

    await store.logout();
    expect(store.isLoggedIn, false);
    expect(store.token, isNull);

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('token'), isNull);
  });
}
