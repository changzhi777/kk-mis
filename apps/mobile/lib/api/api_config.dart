/// V2.0 APP API 配置（后端 admin :8300）
///
/// 双角色：消费者（客户）+ 经销商，共用一 APP 按角色显功能。
/// 接后端 v2 经销商域 API（31 端点）+ v1 CMS/admin（登录/产品等）。
///
/// 开发：Android 模拟器 10.0.2.2 → host localhost；iOS 模拟器用 localhost。
/// 生产：https://nanoai.fun/oa/admin/api/v{1,2}
class ApiConfig {
  ApiConfig._();

  static const String scheme = 'http';
  static const String host = '10.0.2.2'; // Android 模拟器 → host；iOS 用 localhost
  static const int port = 8300;

  static const String v2Base = '/admin/api/v2'; // 经销商域
  static const String v1Base = '/admin/api/v1'; // admin/CMS

  static String get v2Url => '$scheme://$host:$port$v2Base';
  static String get v1Url => '$scheme://$host:$port$v1Base';
}
