import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../lib/pages/login_page.dart';

void main() {
  testWidgets('Login landing page builds smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: LoginPage()));

    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.text('Sesi Ujian Berakhir'), findsOneWidget);
  });
}
