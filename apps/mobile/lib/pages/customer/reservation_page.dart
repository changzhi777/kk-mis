import 'package:flutter/material.dart';

import '../../api/v2_api.dart';

/// 预约出行（GET /tour-groups 团期列表 + POST /reservation 预约 1 人）。
class ReservationPage extends StatefulWidget {
  const ReservationPage({super.key});

  @override
  State<ReservationPage> createState() => _ReservationPageState();
}

class _ReservationPageState extends State<ReservationPage> {
  List<dynamic>? _groups;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final list = await V2Api.listTourGroups();
      setState(() => _groups = list);
    } catch (_) {
      setState(() => _groups = []);
    }
  }

  Future<void> _reserve(Map<String, dynamic> g) async {
    try {
      await V2Api.createReservation(g['id'] as int, peopleCount: 1);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('预约成功')),
        );
      }
      _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('预约失败：$e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('预约出行')),
      body: _groups == null
          ? const Center(child: CircularProgressIndicator())
          : _groups!.isEmpty
              ? const Center(child: Text('暂无可预约团期'))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    itemCount: _groups!.length,
                    itemBuilder: (_, i) {
                      final g = _groups![i] as Map<String, dynamic>;
                      final booked = g['booked'] as int;
                      final capacity = g['capacity'] as int;
                      final left = capacity - booked;
                      return Card(
                        child: ListTile(
                          title: Text(g['title'] as String),
                          subtitle: Text(
                            '${g['start_date'] ?? ''} · 余位 $left/$capacity · ${g['status']}',
                          ),
                          trailing: ElevatedButton(
                            onPressed: left > 0 ? () => _reserve(g) : null,
                            child: const Text('预约'),
                          ),
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}
