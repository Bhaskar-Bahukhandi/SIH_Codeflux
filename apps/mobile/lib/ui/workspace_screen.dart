import "dart:async";

import "package:flutter/material.dart";

import "../app/officer_workspace_service.dart";
import "../auth/officer_session_store.dart";
import "../capture/field_capture_coordinator.dart";
import "../offline/models/sync_state.dart";
import "inspection_screen.dart";
import "sync_summary_formatter.dart";

class WorkspaceScreen extends StatefulWidget {
  const WorkspaceScreen({
    super.key,
    required this.officer,
    required this.workspace,
    required this.captureCoordinator,
    required this.onSignedOut,
  });

  final OfficerSessionContext officer;
  final OfficerWorkspaceService workspace;
  final FieldCaptureCoordinator captureCoordinator;
  final VoidCallback onSignedOut;

  @override
  State<WorkspaceScreen> createState() => _WorkspaceScreenState();
}

class _WorkspaceScreenState extends State<WorkspaceScreen> {
  List<OfficerInspectionWorkspaceItem> _items =
      const <OfficerInspectionWorkspaceItem>[];
  PendingCaptureRecoveryResult? _captureRecovery;
  String? _error;
  bool _loading = true;
  bool _syncing = false;

  @override
  void initState() {
    super.initState();
    _openWorkspace();
  }

  Future<void> _openWorkspace() async {
    try {
      final recovery =
          await widget.captureCoordinator.recoverInterruptedCapture();
      final items = await widget.workspace.listInspections();
      if (!mounted) return;
      setState(() {
        _captureRecovery = recovery;
        _items = items;
        _loading = false;
        _error = null;
      });
      if (recovery.status == PendingCaptureRecoveryStatus.recovered) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              "Recovered the interrupted package image and saved it locally.",
            ),
          ),
        );
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error.toString();
      });
    }
  }

  Future<void> _reload() async {
    try {
      final items = await widget.workspace.listInspections();
      if (!mounted) return;
      setState(() {
        _items = items;
        _error = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  Future<void> _createInspection() async {
    final draft = await showDialog<_NewInspectionDraft>(
      context: context,
      builder: (_) => const _CreateInspectionDialog(),
    );

    if (draft == null || !mounted) {
      return;
    }

    try {
      final created = await widget.workspace.createInspection(
        productName: draft.productName,
        productIdentifier: draft.productIdentifier,
      );
      await _reload();
      if (!mounted) return;

      final route = Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => InspectionScreen(
            inspectionId: created.inspection.id,
            workspace: widget.workspace,
            captureCoordinator: widget.captureCoordinator,
          ),
        ),
      );
      unawaited(
        route.then((_) async {
          if (mounted) {
            await _reload();
          }
        }),
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Could not create inspection: $error")),
        );
      }
    }
  }

  Future<void> _editInspection(
    OfficerInspectionWorkspaceItem item,
  ) async {
    final draft = await showDialog<_NewInspectionDraft>(
      context: context,
      builder: (_) => _EditInspectionDialog(
        productName: item.inspection.productName,
        productIdentifier: item.inspection.productIdentifier,
      ),
    );
    if (draft == null || !mounted) {
      return;
    }

    try {
      await widget.workspace.updateInspectionDetails(
        inspectionId: item.inspection.id,
        productName: draft.productName,
        productIdentifier: draft.productIdentifier,
      );
      await _reload();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            "Inspection details updated locally. Sync to apply them to the server.",
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Could not edit inspection: $error")),
      );
    }
  }

  Future<void> _discardInspection(
    OfficerInspectionWorkspaceItem item,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text("Discard inspection?"),
        content: Text(
          "Discard \"${item.inspection.productName}\"? "
          "It will disappear from this Officer list immediately. "
          "The next sync records an audited discard on the server. "
          "This is available only before preliminary review is queued.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text("Cancel"),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text("Discard"),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) {
      return;
    }

    try {
      await widget.workspace.discardInspection(
        inspectionId: item.inspection.id,
      );
      await _reload();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            "Inspection discarded locally. Sync to apply the audited discard to the server.",
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Could not discard inspection: $error")),
      );
    }
  }

  Future<void> _syncNow() async {
    if (_syncing) return;
    setState(() => _syncing = true);
    try {
      final result = await widget.workspace.syncNow();
      if (!mounted) return;
      if (result.requiresAuthentication) {
        final reauthenticate = await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: const Text("Sign in again"),
            content: const Text(
              "Your saved Officer identity is still available offline, "
              "but the network session has expired. Local drafts have not "
              "been changed. Sign in again to continue synchronization.",
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: const Text("Not now"),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialogContext, true),
                child: const Text("Sign in again"),
              ),
            ],
          ),
        );
        if (reauthenticate == true) {
          await widget.workspace.signOut();
          if (mounted) widget.onSignedOut();
        }
        return;
      }
      await _reload();
      final summary = result.summary!;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(formatSyncDrainSummary(summary)),
        ),
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Sync could not complete: $error")),
        );
      }
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  Future<void> _signOut() async {
    final hasPending = _items.any((item) => !item.syncSummary.isFullySynced);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text("Sign out"),
        content: Text(
          hasPending
              ? "Some inspections are not fully synchronized. Their local "
                  "data will remain on this device and will be visible again "
                  "only after the same Officer signs in."
              : "Local inspection data remains on this device after sign out.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text("Cancel"),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text("Sign out"),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.workspace.signOut();
    if (mounted) widget.onSignedOut();
  }

  Future<void> _discardCaptureMarker() async {
    await widget.captureCoordinator.discardPendingCapture();
    if (!mounted) return;
    setState(() {
      _captureRecovery = const PendingCaptureRecoveryResult(
        status: PendingCaptureRecoveryStatus.none,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final pendingCapture = _captureRecovery?.status ==
        PendingCaptureRecoveryStatus.pendingWithoutRecoveredData;

    return Scaffold(
      appBar: AppBar(
        title: const Text("My inspections"),
        actions: [
          IconButton(
            tooltip: "Sync now",
            onPressed: _syncing ? null : _syncNow,
            icon: _syncing
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync),
          ),
          PopupMenuButton<String>(
            onSelected: (value) {
              if (value == "sign_out") _signOut();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(
                value: "sign_out",
                child: Text("Sign out"),
              ),
            ],
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _createInspection,
        icon: const Icon(Icons.add),
        label: const Text("New inspection"),
      ),
      body: RefreshIndicator(
        onRefresh: _reload,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            Text(
              widget.officer.fullName,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(widget.officer.email),
            const SizedBox(height: 16),
            if (pendingCapture)
              _InterruptedCaptureNotice(onDiscard: _discardCaptureMarker),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  "Workspace error: $_error",
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ),
            if (_loading)
              const Padding(
                padding: EdgeInsets.only(top: 48),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_items.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 48),
                child: Center(
                  child: Text(
                    "No inspections on this device yet.\n"
                    "Create one to start capturing package evidence.",
                    textAlign: TextAlign.center,
                  ),
                ),
              )
            else
              ..._items.map(
                (item) => Column(
                  children: [
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(item.inspection.productName),
                      subtitle: Text(
                        "${item.evidenceCount} image(s) · "
                        "${_stateLabel(item.syncSummary.overallState)}",
                      ),
                      trailing: PopupMenuButton<String>(
                        tooltip: "Inspection actions",
                        enabled: !_syncing,
                        onSelected: (value) {
                          if (value == "edit") {
                            unawaited(_editInspection(item));
                          } else if (value == "discard") {
                            unawaited(_discardInspection(item));
                          }
                        },
                        itemBuilder: (_) => const [
                          PopupMenuItem(
                            value: "edit",
                            child: ListTile(
                              leading: Icon(Icons.edit_outlined),
                              title: Text("Edit details"),
                              contentPadding: EdgeInsets.zero,
                            ),
                          ),
                          PopupMenuItem(
                            value: "discard",
                            child: ListTile(
                              leading: Icon(Icons.delete_outline),
                              title: Text("Discard inspection"),
                              contentPadding: EdgeInsets.zero,
                            ),
                          ),
                        ],
                      ),
                      onTap: () async {
                        await Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => InspectionScreen(
                              inspectionId: item.inspection.id,
                              workspace: widget.workspace,
                              captureCoordinator: widget.captureCoordinator,
                            ),
                          ),
                        );
                        await _reload();
                      },
                    ),
                    const Divider(height: 1),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _stateLabel(SyncState state) {
    return switch (state) {
      SyncState.localOnly => "Local only",
      SyncState.queued => "Waiting to sync",
      SyncState.syncing => "Syncing",
      SyncState.synced => "Synced",
      SyncState.retryRequired => "Needs retry",
      SyncState.conflict => "Needs review",
      SyncState.blocked => "Blocked",
    };
  }
}

class _NewInspectionDraft {
  const _NewInspectionDraft({
    required this.productName,
    this.productIdentifier,
  });

  final String productName;
  final String? productIdentifier;
}

class _CreateInspectionDialog extends StatefulWidget {
  const _CreateInspectionDialog();

  @override
  State<_CreateInspectionDialog> createState() =>
      _CreateInspectionDialogState();
}

class _CreateInspectionDialogState extends State<_CreateInspectionDialog> {
  final _formKey = GlobalKey<FormState>();
  final _productController = TextEditingController();
  final _identifierController = TextEditingController();

  @override
  void dispose() {
    _productController.dispose();
    _identifierController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final productName = _productController.text.trim();
    final identifier = _identifierController.text.trim();
    Navigator.pop(
      context,
      _NewInspectionDraft(
        productName: productName,
        productIdentifier: identifier.isEmpty ? null : identifier,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text("New inspection"),
      content: Form(
        key: _formKey,
        child: SizedBox(
          width: 420,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _productController,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: "Product name",
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return "Product name is required.";
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _identifierController,
                decoration: const InputDecoration(
                  labelText: "Product identifier (optional)",
                ),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text("Cancel"),
        ),
        FilledButton(
          onPressed: _submit,
          child: const Text("Create"),
        ),
      ],
    );
  }
}

class _EditInspectionDialog extends StatefulWidget {
  const _EditInspectionDialog({
    required this.productName,
    this.productIdentifier,
  });

  final String productName;
  final String? productIdentifier;

  @override
  State<_EditInspectionDialog> createState() =>
      _EditInspectionDialogState();
}

class _EditInspectionDialogState extends State<_EditInspectionDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _productController;
  late final TextEditingController _identifierController;

  @override
  void initState() {
    super.initState();
    _productController = TextEditingController(text: widget.productName);
    _identifierController = TextEditingController(
      text: widget.productIdentifier ?? "",
    );
  }

  @override
  void dispose() {
    _productController.dispose();
    _identifierController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    final identifier = _identifierController.text.trim();
    Navigator.pop(
      context,
      _NewInspectionDraft(
        productName: _productController.text.trim(),
        productIdentifier: identifier.isEmpty ? null : identifier,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text("Edit inspection"),
      content: Form(
        key: _formKey,
        child: SizedBox(
          width: 420,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _productController,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: "Product name",
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return "Product name is required.";
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _identifierController,
                decoration: const InputDecoration(
                  labelText: "Product identifier (optional)",
                ),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text("Cancel"),
        ),
        FilledButton(
          onPressed: _submit,
          child: const Text("Save"),
        ),
      ],
    );
  }
}

class _InterruptedCaptureNotice extends StatelessWidget {
  const _InterruptedCaptureNotice({required this.onDiscard});

  final VoidCallback onDiscard;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).colorScheme.outline),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.warning_amber_rounded),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  "A previous image capture was interrupted, but Android "
                  "did not return a recoverable image. Retry that package "
                  "view from the inspection. The marker is kept until you "
                  "discard it.",
                ),
              ),
              TextButton(onPressed: onDiscard, child: const Text("Discard")),
            ],
          ),
        ),
      ),
    );
  }
}
