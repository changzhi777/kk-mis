import 'api_client.dart';

/// V2 业务 API 封装（实名/授权码/权益/套餐/团期/预约）。
class V2Api {
  V2Api._();

  // ── 实名 ──
  static Future<Map<String, dynamic>> verifyRealname(
    String realName,
    String idCardNo,
  ) async {
    final r = await ApiClient.instance.v2.post(
      '/realname/verify',
      data: {'real_name': realName, 'id_card_no': idCardNo},
    );
    return (r.data as Map).cast<String, dynamic>();
  }

  static Future<Map<String, dynamic>> getRealname() async {
    final r = await ApiClient.instance.v2.get('/realname/me');
    return (r.data as Map).cast<String, dynamic>();
  }

  // ── 授权码 ──
  static Future<Map<String, dynamic>> createActivationCode(
    String promoCode,
    int productId,
  ) async {
    final r = await ApiClient.instance.v2.post(
      '/activation/code',
      data: {'promo_code': promoCode, 'product_id': productId},
    );
    return (r.data as Map).cast<String, dynamic>();
  }

  // ── 权益 ──
  static Future<List<dynamic>> listMemberships() async {
    final r = await ApiClient.instance.v2.get('/membership');
    return r.data as List;
  }

  // ── 套餐 ──
  static Future<List<dynamic>> listProducts() async {
    final r = await ApiClient.instance.v2.get('/products');
    return r.data as List;
  }

  // ── 团期 ──
  static Future<List<dynamic>> listTourGroups([int? productId]) async {
    final r = await ApiClient.instance.v2.get(
      '/tour-groups',
      queryParameters: productId != null ? {'product_id': productId} : null,
    );
    return r.data as List;
  }

  // ── 预约 ──
  static Future<Map<String, dynamic>> createReservation(
    int tourGroupId, {
    int? activationCodeId,
    required int peopleCount,
    int hotelQty = 0,
    int carQty = 0,
  }) async {
    final data = <String, dynamic>{
      'tour_group_id': tourGroupId,
      'people_count': peopleCount,
      'hotel_qty': hotelQty,
      'car_qty': carQty,
    };
    if (activationCodeId != null) data['activation_code_id'] = activationCodeId;
    final r = await ApiClient.instance.v2.post('/reservation', data: data);
    return (r.data as Map).cast<String, dynamic>();
  }
}
