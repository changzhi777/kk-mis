import 'package:flutter/material.dart';

import '../../api/v2_api.dart';

/// 经销商月度对账（GET /statement 当月激活明细 + 返点）。
class StatementPage extends StatefulWidget {
  const StatementPage({super.key});

  @override
  State<StatementPage> createState() => _StatementPageState();
}

class _StatementPageState extends State<StatementPage> {
  Map<String, dynamic>? _data;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final d = await V2Api.getStatement();
      setState(() => _data = d);
    } catch (_) {
      setState(() => _data = {});
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('月度对账'),
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
                  Text(
                    '账期：${_data!['period'] ?? ''}',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text('当月消费：¥${_data!['total_sales'] ?? 0}'),
                  if (_data!['rebate'] != null) ...[
                    const Divider(),
                    Text('返点档位：${_data!['rebate']['tier']}'),
                    Text('返点比例：${_data!['rebate']['rebate_pct']}'),
                    Text(
                      '返点金额：¥${_data!['rebate']['amount']}',
                      style: const TextStyle(
                        color: Color(0xFF0D9488),
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text('返点状态：${_data!['rebate']['status']}'),
                  ],
                  const Divider(),
                  const Text(
                    '激活明细',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  ...((_data!['activations'] as List?) ?? []).map(
                    (a) => ListTile(
                      leading: const Icon(
                        Icons.receipt,
                        color: Color(0xFF0D9488),
                      ),
                      title: Text('授权码 ${a['code']}'),
                      subtitle: Text(
                        '¥${a['price']} · ${a['status']} · ${a['activated_at'] ?? ''}',
                      ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
