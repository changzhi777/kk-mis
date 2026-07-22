import 'package:flutter/material.dart';

import '../../api/v2_api.dart';

/// 实名认证页（三要素：姓名 + 身份证号）。
class RealnamePage extends StatefulWidget {
  const RealnamePage({super.key});

  @override
  State<RealnamePage> createState() => _RealnamePageState();
}

class _RealnamePageState extends State<RealnamePage> {
  final _name = TextEditingController();
  final _idCard = TextEditingController();
  String? _status;
  String? _realName;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = await V2Api.getRealname();
      setState(() {
        _status = r['realname_status'] as String?;
        _realName = r['real_name'] as String?;
      });
    } catch (_) {
      // 未实名 getRealname 也返回 unverified，忽略错误
    }
  }

  Future<void> _submit() async {
    if (_name.text.trim().isEmpty || _idCard.text.trim().isEmpty) return;
    setState(() => _loading = true);
    try {
      final r = await V2Api.verifyRealname(
        _name.text.trim(),
        _idCard.text.trim(),
      );
      setState(() {
        _status = r['realname_status'] as String;
        _realName = r['real_name'] as String?;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('实名认证成功')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('失败：$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _idCard.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final verified = _status == 'verified';
    return Scaffold(
      appBar: AppBar(title: const Text('实名认证')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: verified
            ? Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(
                      Icons.verified_user,
                      size: 64,
                      color: Color(0xFF0D9488),
                    ),
                    const SizedBox(height: 16),
                    Text('已实名：${_realName ?? ''}'),
                  ],
                ),
              )
            : Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  TextField(
                    controller: _name,
                    decoration: const InputDecoration(
                      labelText: '真实姓名',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _idCard,
                    decoration: const InputDecoration(
                      labelText: '身份证号',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _loading ? null : _submit,
                      child: Text(_loading ? '提交中...' : '提交认证'),
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}
