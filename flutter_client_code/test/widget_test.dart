import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../lib/pages/native_login_page.dart';

void main() {
  testWidgets('Native APK login page builds smoke test', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: NativeLoginPage()));
    await tester.pump();

    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.text('SIAB1'), findsOneWidget);
    expect(find.text('Silakan login untuk memulai ujian'), findsOneWidget);
    expect(find.text('MASUK'), findsOneWidget);
    expect(find.textContaining('man1rokanhulu.cloud'), findsNothing);
    expect(find.text('Server ujian belum siap'), findsNothing);
  });
}
