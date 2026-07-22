import 'package:flutter/material.dart';

import '../../api/v2_api.dart';

/// 我的权益（GET /membership 列表，active/used/refunded）。
class MembershipPage extends StatefulWidget {
  const MembershipPage({super.key});

  @override
  State<MembershipPage> createState() => _MembershipPageState();
}

class _MembershipPageState extends State<MembershipPage> {
  List<dynamic>? _list;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final list = await V2Api.listMemberships();
      setState(() => _list = list);
    } catch (_) {
      setState(() => _list = []);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('我的权益'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _list == null
          ? const Center(child: CircularProgressIndicator())
          : _list!.isEmpty
              ? const Center(child: Text('暂无权益\n（经销商激活后生效）', textAlign: TextAlign.center))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    itemCount: _list!.length,
                    itemBuilder: (_, i) {
                      final m = _list![i] as Map<String, dynamic>;
                      final status = m['status'] as String;
                      final color = status == 'active'
                          ? const Color(0xFF0D9488)
                          : status == 'used'
                              ? Colors.grey
                              : Colors.orange;
                      return ListTile(
                        leading: Icon(Icons.card_membership, color: color),
                        title: Text('套餐 #${m['product_id']}'),
                        subtitle: Text('${m['activated_at'] ?? ''}'),
                        trailing: Chip(label: Text(status)),
                      );
                    },
                  ),
                ),
    );
  }
}
