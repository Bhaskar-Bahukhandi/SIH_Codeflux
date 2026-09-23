import "dart:async";

import "package:flutter/material.dart";

import "app/app_dependencies.dart";
import "app/codeflux_app.dart";

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  const configuredUrl = String.fromEnvironment("CODEFLUX_API_URL");
  if (configuredUrl.trim().isEmpty) {
    runApp(const _ConfigurationErrorApp());
    return;
  }

  final uri = Uri.tryParse(configuredUrl);
  if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
    runApp(const _ConfigurationErrorApp());
    return;
  }

  final dependencies = await AppDependencies.create(
    serverBaseUri: uri,
  );
  runApp(_DisposableCodefluxRoot(dependencies: dependencies));
}

class _DisposableCodefluxRoot extends StatefulWidget {
  const _DisposableCodefluxRoot({
    required this.dependencies,
  });

  final AppDependencies dependencies;

  @override
  State<_DisposableCodefluxRoot> createState() =>
      _DisposableCodefluxRootState();
}

class _DisposableCodefluxRootState extends State<_DisposableCodefluxRoot> {
  @override
  void dispose() {
    unawaited(widget.dependencies.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return CodefluxApp(dependencies: widget.dependencies);
  }
}

class _ConfigurationErrorApp extends StatelessWidget {
  const _ConfigurationErrorApp();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "CODEFLUX",
      home: Scaffold(
        appBar: AppBar(title: const Text("CODEFLUX")),
        body: const Padding(
          padding: EdgeInsets.all(24),
          child: Center(
            child: Text(
              "API address is not configured.\n\n"
              "Start the app with --dart-define="
              "CODEFLUX_API_URL=https://your-api.example/\n\n"
              "No demo or hard-coded server is used.",
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ),
    );
  }
}
