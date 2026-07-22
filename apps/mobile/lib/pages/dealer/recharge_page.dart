import 'package:flutter/material.dart';

import '../../api/v2_api.dart';

/// 经销商充值（mock 渠道立即到账；真支付微信/支付宝待 M4.6 接入）。
class RechargePage extends StatefulWidget {
  const RechargePage({super.key});

  @override
  State<RechargePage> createState() => _RechargePageState();
}

class _RechargePageState extends State<RechargePage> {
  num _amount = 100;
  bool _loading = false;

  static const _presets = [100, 500, 1000, 5000];

  Future<void> _recharge() async {
    if (_amount <= 0) return;
    setState(() => _loading = true);
    try {
      await V2Api.recharge(_amount);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('充值成功 ¥$_amount')),
        );
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('充值失败：$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('充值')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('选择金额（元）'),
            const SizedBox(height: 12),
            Wrap(
              spacing: 12,
              children: _presets
                  .map(
                    (v) => ChoiceChip(
                      label: Text('¥$v'),
                      selected: _amount == v,
                      onSelected: (_) => setState(() => _amount = v),
                    ),
                  )
                  .toList(),
            ),
            const SizedBox(height: 24),
            const Text('当前渠道：mock（立即到账，测试用）'),
            const SizedBox(height: 8),
            const Text(
              '微信/支付宝真支付待商户密钥接入',
              style: TextStyle(color: Colors.grey, fontSize: 12),
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _loading ? null : _recharge,
                child: Text(_loading ? '充值中...' : '确认充值 ¥$_amount'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
