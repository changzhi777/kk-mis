import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

/// 通用扫码页（mobile_scanner）：扫到首个 code → pop 返回内容。
///
/// 消费者扫经销商推广码（填授权码页 promo 字段）；
/// 经销商扫客户授权码（填激活页 code 字段）。
class ScanPage extends StatefulWidget {
  final String? title;
  const ScanPage({super.key, this.title});

  @override
  State<ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends State<ScanPage> {
  final _controller = MobileScannerController();
  bool _done = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_done) return;
    final list = capture.barcodes;
    if (list.isEmpty) return;
    final raw = list.first.rawValue;
    if (raw == null || raw.isEmpty) return;
    _done = true;
    Navigator.of(context).pop(raw);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title ?? '扫码'),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_on),
            onPressed: () => _controller.toggleTorch(),
          ),
          IconButton(
            icon: const Icon(Icons.flip_camera_ios),
            onPressed: () => _controller.switchCamera(),
          ),
        ],
      ),
      body: Stack(
        children: [
          MobileScanner(controller: _controller, onDetect: _onDetect),
          // 扫码框示意
          Center(
            child: Container(
              width: 250,
              height: 250,
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFF0D9488), width: 2),
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
