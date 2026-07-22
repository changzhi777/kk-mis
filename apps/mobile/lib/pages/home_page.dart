import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../stores/auth_store.dart';
import 'customer/activation_code_page.dart';
import 'customer/realname_page.dart';
import 'dealer/activate_page.dart';
import 'dealer/dashboard_page.dart';
import 'dealer/recharge_page.dart';

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

  void _push(BuildContext context, Widget page) =>
      Navigator.push(context, MaterialPageRoute(builder: (_) => page));

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        ListTile(
          leading: const Icon(Icons.dashboard, color: Color(0xFF0D9488)),
          title: const Text('工作台'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _push(context, const DealerDashboardPage()),
        ),
        ListTile(
          leading: const Icon(
            Icons.account_balance_wallet,
            color: Color(0xFF0D9488),
          ),
          title: const Text('充值'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _push(context, const RechargePage()),
        ),
        ListTile(
          leading: const Icon(
            Icons.qr_code_scanner,
            color: Color(0xFF0D9488),
          ),
          title: const Text('扫授权码激活'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _push(context, const ActivatePage()),
        ),
        const _MenuTile(icon: Icons.receipt_long, title: '月度对账'),
        const _MenuTile(icon: Icons.settings, title: '经销商申请 / 资质'),
      ],
    );
  }
}

class _CustomerHome extends StatelessWidget {
  const _CustomerHome();

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        ListTile(
          leading: const Icon(Icons.qr_code, color: Color(0xFF0D9488)),
          title: const Text('生成授权码（推广码+套餐）'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const ActivationCodePage()),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.badge, color: Color(0xFF0D9488)),
          title: const Text('实名认证'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const RealnamePage()),
          ),
        ),
        const _MenuTile(icon: Icons.card_membership, title: '我的权益'),
        const _MenuTile(icon: Icons.event, title: '预约出行'),
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
