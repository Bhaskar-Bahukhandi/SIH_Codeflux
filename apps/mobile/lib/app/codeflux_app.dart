import "package:flutter/material.dart";

import "../auth/officer_session_store.dart";
import "app_dependencies.dart";
import "../ui/login_screen.dart";
import "../ui/workspace_screen.dart";

class CodefluxApp extends StatefulWidget {
  const CodefluxApp({
    super.key,
    required this.dependencies,
  });

  final AppDependencies dependencies;

  @override
  State<CodefluxApp> createState() => _CodefluxAppState();
}

class _CodefluxAppState extends State<CodefluxApp> {
  int _sessionRevision = 0;

  void _refreshSession() {
    setState(() {
      _sessionRevision += 1;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "CODEFLUX",
      theme: ThemeData(
        useMaterial3: true,
        visualDensity: VisualDensity.standard,
      ),
      home: _SessionGate(
        key: ValueKey<int>(_sessionRevision),
        dependencies: widget.dependencies,
        onSessionChanged: _refreshSession,
      ),
    );
  }
}

class _SessionGate extends StatelessWidget {
  const _SessionGate({
    super.key,
    required this.dependencies,
    required this.onSessionChanged,
  });

  final AppDependencies dependencies;
  final VoidCallback onSessionChanged;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<OfficerSessionContext?>(
      future: dependencies.workspace.currentOfficerIdentity(),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snapshot.hasError) {
          return Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  "Could not open the local Officer workspace.\n"
                  + snapshot.error.toString(),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          );
        }

        final officer = snapshot.data;
        if (officer == null) {
          return LoginScreen(
            authClient: dependencies.authClient,
            onAuthenticated: onSessionChanged,
          );
        }

        return WorkspaceScreen(
          officer: officer,
          workspace: dependencies.workspace,
          captureCoordinator: dependencies.captureCoordinator,
          onSignedOut: onSessionChanged,
        );
      },
    );
  }
}
