import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../stores/auth_store.dart';

/// 首页：按角色（经销商/消费者）显功能入口（M4.2 骨架，M4.3/4.4 接 API）。
class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final isDealer = context.watch<AuthStore>().isDealer;
    return Scaffold(
      appBar: AppBar(
        title: Text(isDealer ? '经销商工作台' : '我的'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthStore>().logout(),
          ),
        ],
      ),
      body: isDealer ? const _DealerHome() : const _CustomerHome(),
    );
  }
}

class _DealerHome extends StatelessWidget {
  const _DealerHome();

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: const [
        _MenuTile(icon: Icons.dashboard, title: '工作台'),
        _MenuTile(icon: Icons.account_balance_wallet, title: '充值 / 余额'),
        _MenuTile(icon: Icons.qr_code_scanner, title: '扫授权码激活'),
        _MenuTile(icon: Icons.receipt_long, title: '月度对账'),
        _MenuTile(icon: Icons.settings, title: '经销商申请 / 资质'),
      ],
    );
  }
}

class _CustomerHome extends StatelessWidget {
  const _CustomerHome();

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: const [
        _MenuTile(icon: Icons.qr_code, title: '扫经销商推广码'),
        _MenuTile(icon: Icons.badge, title: '实名认证'),
        _MenuTile(icon: Icons.card_membership, title: '我的权益'),
        _MenuTile(icon: Icons.event, title: '预约出行'),
      ],
    );
  }
}

class _MenuTile extends StatelessWidget {
  final IconData icon;
  final String title;
  const _MenuTile({required this.icon, required this.title});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: const Color(0xFF0D9488)),
      title: Text(title),
      trailing: const Icon(Icons.chevron_right),
      onTap: () {
        // TODO M4.3/M4.4：接具体页面
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$title（M4.3/4.4 待实现）')),
        );
      },
    );
  }
}
