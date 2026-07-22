import 'package:flutter/material.dart';

import '../../api/v2_api.dart';

/// 扫客户授权码 → 发起激活（冻结经销商余额，待客户二次确认）。
class ActivatePage extends StatefulWidget {
  const ActivatePage({super.key});

  @override
  State<ActivatePage> createState() => _ActivatePageState();
}

class _ActivatePageState extends State<ActivatePage> {
  final _code = TextEditingController();
  bool _loading = false;
  Map<String, dynamic>? _result;

  Future<void> _initiate() async {
    final code = _code.text.trim();
    if (code.isEmpty) return;
    setState(() {
      _loading = true;
      _result = null;
    });
    try {
      final r = await V2Api.initiateActivation(code);
      setState(() => _result = r);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('激活失败：$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('扫授权码激活')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _code,
              decoration: const InputDecoration(
                labelText: '客户授权码（6 位）',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.qr_code_scanner),
              ),
              keyboardType: TextInputType.number,
              maxLength: 6,
            ),
            const SizedBox(height: 8),
            // TODO M4.4续：接相机扫码（mobile_scanner）
            const Text(
              '输入客户出示的 6 位授权码（或后续接相机扫码）',
              style: TextStyle(color: Colors.grey, fontSize: 12),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _loading ? null : _initiate,
                child: Text(_loading ? '处理中...' : '发起激活'),
              ),
            ),
            if (_result != null) ...[
              const SizedBox(height: 24),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(
                            Icons.check_circle,
                            color: Color(0xFF0D9488),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '已发起，状态：${_result!['status']}',
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text('套餐价：¥${_result!['price']}'),
                      const SizedBox(height: 4),
                      const Text(
                        '已冻结余额，等待客户在 APP 二次确认',
                        style: TextStyle(color: Colors.grey, fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
