import 'package:flutter/material.dart';

import '../../api/v2_api.dart';

/// 经销商工作台（余额/冻结/累计/激活数/返点）+ 月结按钮。
class DealerDashboardPage extends StatefulWidget {
  const DealerDashboardPage({super.key});

  @override
  State<DealerDashboardPage> createState() => _DealerDashboardPageState();
}

class _DealerDashboardPageState extends State<DealerDashboardPage> {
  Map<String, dynamic>? _data;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final d = await V2Api.getDashboard();
      setState(() => _data = d);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('加载失败：$e')));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _settle() async {
    try {
      await V2Api.settleRebate();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('当月返点结算成功')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('月结失败：$e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('经销商工作台'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _data == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Card(
                    child: ListTile(
                      leading: const Icon(
                        Icons.account_balance_wallet,
                        color: Color(0xFF0D9488),
                        size: 32,
                      ),
                      title: const Text('可用余额'),
                      trailing: Text(
                        '¥ ${_data!['balance']}',
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF0D9488),
                        ),
                      ),
                    ),
                  ),
                  _row('冻结', '¥ ${_data!['frozen']}'),
                  _row('累计充值', '¥ ${_data!['total_recharged']}'),
                  _row('累计消耗', '¥ ${_data!['total_consumed']}'),
                  _row('已激活客户', '${_data!['activated_count']}'),
                  _row('累计返点', '¥ ${_data!['total_rebate']}'),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: _loading ? null : _settle,
                    icon: const Icon(Icons.savings),
                    label: const Text('触发当月返点结算'),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _row(String title, String value) => ListTile(
        title: Text(title),
        trailing: Text(value, style: const TextStyle(fontSize: 16)),
      );
}
