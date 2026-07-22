import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'pages/home_page.dart';
import 'pages/login_page.dart';
import 'stores/auth_store.dart';

void main() {
  runApp(const DhtsApp());
}

class DhtsApp extends StatelessWidget {
  const DhtsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthStore()..init()),
      ],
      child: MaterialApp(
        title: '大华天麓',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorSchemeSeed: const Color(0xFF0D9488),
          useMaterial3: true,
        ),
        home: const _Router(),
      ),
    );
  }
}

/// 启动路由：loading → 已登录 HomePage / 未登录 LoginPage。
class _Router extends StatelessWidget {
  const _Router();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthStore>();
    if (auth.loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return auth.isLoggedIn ? const HomePage() : const LoginPage();
  }
}
