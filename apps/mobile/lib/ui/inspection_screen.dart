import "dart:io";

import "package:flutter/material.dart";

import "../app/officer_workspace_service.dart";
import "../capture/evidence_acquisition_service.dart";
import "../capture/field_capture_coordinator.dart";
import "../offline/models/local_records.dart";
import "../offline/models/sync_state.dart";

class InspectionScreen extends StatefulWidget {
  const InspectionScreen({
    super.key,
    required this.inspectionId,
    required this.workspace,
    required this.captureCoordinator,
  });

  final String inspectionId;
  final OfficerWorkspaceService workspace;
  final FieldCaptureCoordinator captureCoordinator;

  @override
  State<InspectionScreen> createState() => _InspectionScreenState();
}

class _InspectionScreenState extends State<InspectionScreen> {
  OfficerInspectionWorkspaceItem? _item;
  List<LocalEvidenceRecord> _evidence = const <LocalEvidenceRecord>[];
  String? _error;
  bool _loading = true;
  bool _busy = false;

  static const _views = <String>[
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom",
    "detail",
    "other",
  ];

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    try {
      final item = await widget.workspace.inspection(widget.inspectionId);
      final evidence = await widget.workspace.listEvidence(widget.inspectionId);
      if (!mounted) return;
      setState(() {
        _item = item;
        _evidence = evidence;
        _error = null;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  Future<void> _addPackageView() async {
    final view = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(
              title: Text("Which side are you capturing?"),
              subtitle: Text(
                "Choose the package view that matches the image.",
              ),
            ),
            ..._views.map(
              (value) => ListTile(
                title: Text(_viewLabel(value)),
                onTap: () => Navigator.pop(sheetContext, value),
              ),
            ),
          ],
        ),
      ),
    );
    if (view == null || !mounted) return;
    await _captureView(view);
  }

  Future<void> _captureView(
    String view, {
    LocalEvidenceRecord? replacing,
  }) async {
    final source = await showModalBottomSheet<EvidenceSource>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined),
              title: const Text("Take photo"),
              subtitle: const Text("Open the device camera"),
              onTap: () => Navigator.pop(
                sheetContext,
                EvidenceSource.camera,
              ),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text("Choose from gallery"),
              subtitle: const Text("Use an existing package image"),
              onTap: () => Navigator.pop(
                sheetContext,
                EvidenceSource.gallery,
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (source == null || !mounted) return;

    setState(() => _busy = true);
    try {
      final saved = replacing == null
          ? await widget.captureCoordinator.acquireAndAttach(
              inspectionId: widget.inspectionId,
              viewType: view,
              source: source,
            )
          : await widget.captureCoordinator.replaceAndAttach(
              inspectionId: widget.inspectionId,
              evidenceId: replacing.id,
              viewType: view,
              source: source,
            );
      if (saved) {
        await _reload();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                replacing == null
                    ? "${_viewLabel(view)} image saved locally and queued."
                    : "${_viewLabel(view)} image replaced. Sync to apply the evidence change.",
              ),
            ),
          );
        }
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              replacing == null
                  ? "Could not save package image: $error"
                  : "Could not replace package image: $error",
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _removeEvidence(LocalEvidenceRecord record) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text("Remove image?"),
        content: Text(
          "Remove the \"${_viewLabel(record.viewType)}\" image from this inspection? "
          "It will no longer be used for OCR or preliminary checks. "
          "If it was already uploaded, CODEFLUX keeps the server evidence in the audit trail "
          "and records it as discarded.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text("Cancel"),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text("Remove"),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _busy = true);
    try {
      await widget.workspace.removeEvidence(
        inspectionId: widget.inspectionId,
        evidenceId: record.id,
      );
      await _reload();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            "Image removed from active evidence. Sync to apply any server-side discard.",
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Could not remove image: $error")),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _queueForReview() async {
    var intendedForRetailSale = true;
    var industrialOrInstitutional = false;
    var exceedsThreshold = false;

    final accepted = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text("Applicability context"),
          content: SizedBox(
            width: 480,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "Record the factual context used by the current "
                    "preliminary Legal Metrology rule pack. These answers "
                    "do not themselves create a compliance finding.",
                  ),
                  const SizedBox(height: 12),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text("Intended for retail sale"),
                    value: intendedForRetailSale,
                    onChanged: (value) => setDialogState(
                      () => intendedForRetailSale = value,
                    ),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text(
                      "Industrial or institutional consumer",
                    ),
                    value: industrialOrInstitutional,
                    onChanged: (value) => setDialogState(
                      () => industrialOrInstitutional = value,
                    ),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text("Package exceeds 25 kg or 25 L"),
                    value: exceedsThreshold,
                    onChanged: (value) => setDialogState(
                      () => exceedsThreshold = value,
                    ),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text("Cancel"),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text("Queue for review"),
            ),
          ],
        ),
      ),
    );
    if (accepted != true || !mounted) return;

    setState(() => _busy = true);
    try {
      await widget.workspace.queueForReview(
        inspectionId: widget.inspectionId,
        ruleContext: <String, Object?>{
          "intended_for_retail_sale": intendedForRetailSale,
          "industrial_or_institutional_consumer":
              industrialOrInstitutional,
          "package_exceeds_25kg_or_25l": exceedsThreshold,
        },
      );
      await _reload();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              "Processing, preliminary rule evaluation and submission "
              "have been queued. Use Sync when connectivity is available.",
            ),
          ),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Could not queue review: $error")),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = _item;
    return Scaffold(
      appBar: AppBar(
        title: Text(item?.inspection.productName ?? "Inspection"),
      ),
      floatingActionButton: item == null
          ? null
          : FloatingActionButton.extended(
              onPressed: _busy ? null : _addPackageView,
              icon: const Icon(Icons.add_a_photo_outlined),
              label: const Text("Add image"),
            ),
      body: RefreshIndicator(
        onRefresh: _reload,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            if (_loading)
              const Padding(
                padding: EdgeInsets.only(top: 48),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null)
              Text(
                "Inspection error: $_error",
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                ),
              )
            else if (item != null) ...[
              Text(
                item.inspection.productName,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              if (item.inspection.productIdentifier != null)
                Text(item.inspection.productIdentifier!),
              const SizedBox(height: 8),
              Text(
                "Sync: ${_stateLabel(item.syncSummary.overallState)}",
              ),
              Text("Images: ${item.evidenceCount}"),
              const SizedBox(height: 24),
              Row(
                children: [
                  Text(
                    "Package images",
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: _busy ? null : _addPackageView,
                    icon: const Icon(Icons.add),
                    label: const Text("Add"),
                  ),
                ],
              ),
              if (_evidence.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 20),
                  child: Text(
                    "No package images saved yet. Capture multiple views "
                    "so declarations can be checked against the available evidence.",
                  ),
                )
              else
                ..._evidence.map(
                  (record) => Column(
                    children: [
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: SizedBox(
                            width: 64,
                            height: 64,
                            child: Image.file(
                              File(record.localPath),
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => const ColoredBox(
                                color: Colors.black12,
                                child: Icon(Icons.broken_image_outlined),
                              ),
                            ),
                          ),
                        ),
                        title: Text(_viewLabel(record.viewType)),
                        subtitle: Text(
                          "${record.sizeBytes} bytes · "
                          "${_stateLabel(record.syncState)}",
                        ),
                        trailing: PopupMenuButton<String>(
                          tooltip: "Image actions",
                          enabled: !_busy,
                          onSelected: (value) {
                            if (value == "replace") {
                              _captureView(
                                record.viewType,
                                replacing: record,
                              );
                            } else if (value == "remove") {
                              _removeEvidence(record);
                            }
                          },
                          itemBuilder: (_) => const [
                            PopupMenuItem(
                              value: "replace",
                              child: ListTile(
                                leading: Icon(Icons.autorenew),
                                title: Text("Replace image"),
                                contentPadding: EdgeInsets.zero,
                              ),
                            ),
                            PopupMenuItem(
                              value: "remove",
                              child: ListTile(
                                leading: Icon(Icons.delete_outline),
                                title: Text("Remove image"),
                                contentPadding: EdgeInsets.zero,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const Divider(height: 1),
                    ],
                  ),
                ),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: _busy ? null : _queueForReview,
                icon: const Icon(Icons.rule_folder_outlined),
                label: const Text("Queue preliminary review"),
              ),
              const SizedBox(height: 8),
              const Text(
                "This queues evidence processing and preliminary checks. "
                "Officer verification remains the decision gate.",
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }

  static String _viewLabel(String value) {
    return switch (value) {
      "front" => "Front",
      "back" => "Back",
      "left" => "Left side",
      "right" => "Right side",
      "top" => "Top",
      "bottom" => "Bottom",
      "detail" => "Declaration detail",
      "other" => "Other view",
      _ => value,
    };
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
