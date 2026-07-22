import 'dart:async';

import 'package:flutter/material.dart';

import '../../api/v2_api.dart';
import '../scan_page.dart';

/// 生成授权码页：输入经销商推广码 + 选套餐 → 生成 6 位授权码（10min 倒计时）。
///
/// 客户把此 code 出示给经销商扫码激活（经销商付费，客户免费体验）。
class ActivationCodePage extends StatefulWidget {
  const ActivationCodePage({super.key});

  @override
  State<ActivationCodePage> createState() => _ActivationCodePageState();
}

class _ActivationCodePageState extends State<ActivationCodePage> {
  final _promo = TextEditingController();
  List<dynamic> _products = [];
  int? _selectedProduct;
  Map<String, dynamic>? _code;
  int _countdown = 0;
  Timer? _timer;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _loadProducts();
  }

  Future<void> _loadProducts() async {
    try {
      final list = await V2Api.listProducts();
      setState(() => _products = list);
    } catch (_) {}
  }

  Future<void> _generate() async {
    if (_promo.text.trim().isEmpty || _selectedProduct == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请填推广码 + 选套餐')),
      );
      return;
    }
    setState(() => _loading = true);
    try {
      final r = await V2Api.createActivationCode(
        _promo.text.trim(),
        _selectedProduct!,
      );
      setState(() => _code = r);
      _startCountdown(r['expires_at'] as String);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('生成失败：$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _startCountdown(String expiresIso) {
    _timer?.cancel();
    final expires = DateTime.parse(expiresIso).toLocal();
    _updateCountdown(expires);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!_updateCountdown(expires)) t.cancel();
    });
  }

  bool _updateCountdown(DateTime expires) {
    final left = expires.difference(DateTime.now()).inSeconds;
    setState(() => _countdown = left > 0 ? left : 0);
    return _countdown > 0;
  }

  @override
  void dispose() {
    _timer?.cancel();
    _promo.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('生成授权码')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: _code == null ? _buildForm() : _buildCode(),
      ),
    );
  }

  Widget _buildForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _promo,
          decoration: InputDecoration(
            labelText: '经销商推广码',
            border: const OutlineInputBorder(),
            suffixIcon: IconButton(
              icon: const Icon(Icons.qr_code_scanner),
              onPressed: () async {
                final result = await Navigator.push<String>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const ScanPage(title: '扫经销商推广码'),
                  ),
                );
                if (result != null) _promo.text = result;
              },
            ),
          ),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<int>(
          initialValue: _selectedProduct,
          decoration: const InputDecoration(
            labelText: '选择套餐',
            border: OutlineInputBorder(),
          ),
          items: _products
          .map(
                (p) => DropdownMenuItem(
              value: p['id'] as int,
              child: Text(p['title'] as String),
            ),
          )
          .toList(),
          onChanged: (v) => setState(() => _selectedProduct = v),
        ),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: _loading ? null : _generate,
            child: Text(_loading ? '生成中...' : '生成授权码'),
          ),
        ),
      ],
    );
  }

  Widget _buildCode() {
    final expired = _countdown <= 0;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text('授权码', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text(
            _code!['code'] as String,
            style: const TextStyle(
              fontSize: 48,
              fontWeight: FontWeight.bold,
              letterSpacing: 8,
              color: Color(0xFF0D9488),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            expired ? '已过期' : '剩余 $_countdown 秒',
            style: TextStyle(color: expired ? Colors.red : Colors.grey),
          ),
          const SizedBox(height: 8),
          Text(
            '套餐价：${_code!['price']} 元',
            style: const TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 8),
          const Text(
            '出示给经销商扫码激活',
            style: TextStyle(color: Colors.grey, fontSize: 12),
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => setState(() => _code = null),
              child: const Text('重新生成'),
            ),
          ),
        ],
      ),
    );
  }
}
