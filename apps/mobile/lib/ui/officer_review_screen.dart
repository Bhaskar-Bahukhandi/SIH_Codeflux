import "package:flutter/material.dart";

import "../app/officer_workspace_service.dart";
import "../review/officer_review_models.dart";

class OfficerReviewScreen extends StatefulWidget {
  const OfficerReviewScreen({
    super.key,
    required this.inspectionId,
    required this.workspace,
  });

  final String inspectionId;
  final OfficerWorkspaceService workspace;

  @override
  State<OfficerReviewScreen> createState() => _OfficerReviewScreenState();
}

class _OfficerReviewScreenState extends State<OfficerReviewScreen> {
  OfficerReviewState? _state;
  String? _error;
  bool _loading = true;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final state = await widget.workspace.loadOfficerReviewState(
        widget.inspectionId,
      );
      if (!mounted) return;
      setState(() {
        _state = state;
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

  Future<bool> _syncQueuedAction() async {
    final result = await widget.workspace.syncNow();
    if (result.requiresAuthentication) {
      throw StateError("Officer session has expired. Sign in again.");
    }

    final summary = result.summary;
    if (summary == null) {
      return false;
    }
    return summary.retryScheduled == 0 &&
        summary.reconciliationRequired == 0 &&
        summary.conflicts == 0 &&
        summary.blocked == 0;
  }

  Future<void> _recordReview(
    OfficerRuleResult result, {
    required String decision,
    Map<String, Object?>? correctedValue,
    String? note,
  }) async {
    setState(() => _busy = true);
    try {
      await widget.workspace.queueOfficerReview(
        inspectionId: widget.inspectionId,
        ruleEvaluationResultId: result.id,
        decision: decision,
        correctedValue: correctedValue,
        note: note,
      );
      final synced = await _syncQueuedAction();
      await _load();
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            synced
                ? "Officer review saved."
                : "Officer review is queued but sync is not complete yet.",
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Could not save Officer review: $error")),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _accept(OfficerRuleResult result) async {
    var note = "";
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text("Accept machine result?"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              "Accept only after checking the package evidence yourself.",
            ),
            const SizedBox(height: 12),
            TextField(
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: "Officer note (optional)",
                border: OutlineInputBorder(),
              ),
              onChanged: (value) => note = value,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text("Cancel"),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text("Accept"),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;
    await _recordReview(
      result,
      decision: "accepted",
      note: note.trim().isEmpty ? null : note.trim(),
    );
  }

  Future<void> _correct(OfficerRuleResult result) async {
    final correction = await showDialog<_CorrectionDraft>(
      context: context,
      builder: (_) => _CorrectionDialog(result: result),
    );
    if (correction == null || !mounted) return;

    await _recordReview(
      result,
      decision: "corrected",
      correctedValue: correction.value,
      note: correction.note,
    );
  }

  Future<void> _recheck(OfficerRuleResult result) async {
    var note = "";
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text("Request recheck?"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              "This returns the inspection to Draft so package evidence "
              "can be added or replaced before running the checks again.",
            ),
            const SizedBox(height: 12),
            TextField(
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: "Reason for recheck",
                border: OutlineInputBorder(),
              ),
              onChanged: (value) => note = value,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text("Cancel"),
          ),
          FilledButton(
            onPressed: () {
              if (note.trim().isEmpty) {
                return;
              }
              Navigator.pop(dialogContext, true);
            },
            child: const Text("Request recheck"),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;
    await _recordReview(
      result,
      decision: "recheck_required",
      note: note.trim(),
    );
  }

  Future<void> _finalize() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text("Finalize inspection?"),
        content: const Text(
          "Finalization locks the reviewed result set and creates the "
          "evidence-backed inspection report. This action is not editable.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text("Cancel"),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text("Finalize"),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _busy = true);
    try {
      await widget.workspace.queueFinalization(
        inspectionId: widget.inspectionId,
      );
      final synced = await _syncQueuedAction();
      await _load();
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            synced
                ? "Inspection finalized."
                : "Finalization is queued but sync is not complete yet.",
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Could not finalize inspection: $error")),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = _state;
    return Scaffold(
      appBar: AppBar(title: const Text("Officer review")),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          children: [
            if (_loading)
              const Padding(
                padding: EdgeInsets.only(top: 64),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null) ...[
              Text(
                "Review error: $_error",
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text("Retry"),
              ),
            ] else if (state != null) ...[
              _ReviewStatusCard(state: state),
              const SizedBox(height: 16),
              if (state.isPendingReview) ...[
                Text(
                  "Preliminary rule results",
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                const Text(
                  "The automated result is preliminary. Review the package "
                  "evidence before accepting or correcting a result.",
                ),
                const SizedBox(height: 12),
                for (final result in state.results)
                  _RuleResultCard(
                    result: result,
                    review: state.latestReviews[result.id],
                    busy: _busy,
                    onAccept:
                        result.canAccept ? () => _accept(result) : null,
                    onCorrect:
                        result.canCorrect ? () => _correct(result) : null,
                    onRecheck: () => _recheck(result),
                  ),
                const SizedBox(height: 12),
                if (!state.canFinalize)
                  const Text(
                    "Finalize becomes available after every result has a "
                    "valid Officer resolution. Use Recheck when the "
                    "current evidence is not sufficient to resolve a result.",
                    textAlign: TextAlign.center,
                  ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed:
                      _busy || !state.canFinalize ? null : _finalize,
                  icon: const Icon(Icons.verified_outlined),
                  label: const Text("Finalize inspection"),
                ),
              ] else if (state.isFinalized) ...[
                const SizedBox(height: 8),
                const Icon(Icons.verified, size: 52),
                const SizedBox(height: 12),
                Text(
                  "Inspection finalized",
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                const Text(
                  "The immutable evidence-backed report is now available "
                  "to authorized users in the Supervisor dashboard.",
                  textAlign: TextAlign.center,
                ),
                if (state.reportId != null) ...[
                  const SizedBox(height: 12),
                  SelectableText(
                    "Report ID: ${state.reportId}",
                    textAlign: TextAlign.center,
                  ),
                ],
              ] else ...[
                const Text(
                  "This inspection is not currently awaiting Officer review.",
                  textAlign: TextAlign.center,
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _ReviewStatusCard extends StatelessWidget {
  const _ReviewStatusCard({required this.state});

  final OfficerReviewState state;

  @override
  Widget build(BuildContext context) {
    final label = switch (state.status) {
      "pending_review" => "Pending Officer review",
      "finalized" => "Finalized",
      "draft" => "Draft",
      "discarded" => "Discarded",
      _ => state.status,
    };

    return Card(
      child: ListTile(
        leading: Icon(
          state.isFinalized
              ? Icons.verified_outlined
              : Icons.fact_check_outlined,
        ),
        title: Text(label),
        subtitle: Text(
          state.isPendingReview
              ? "${state.latestReviews.length} of "
                  "${state.results.length} result(s) reviewed"
              : "Inspection ${state.inspectionId}",
        ),
      ),
    );
  }
}

class _RuleResultCard extends StatelessWidget {
  const _RuleResultCard({
    required this.result,
    required this.review,
    required this.busy,
    required this.onAccept,
    required this.onCorrect,
    required this.onRecheck,
  });

  final OfficerRuleResult result;
  final OfficerRuleReview? review;
  final bool busy;
  final VoidCallback? onAccept;
  final VoidCallback? onCorrect;
  final VoidCallback onRecheck;

  @override
  Widget build(BuildContext context) {
    final currentReview = review;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _declarationLabel(result.declarationType),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 4),
            Text("${result.ruleId} · ${result.provision}"),
            const SizedBox(height: 10),
            _StatusChip(status: result.status),
            const SizedBox(height: 10),
            Text(result.explanation),
            if (currentReview != null) ...[
              const Divider(height: 24),
              Text(
                "Officer decision: "
                "${_decisionLabel(currentReview.decision)}",
                style: Theme.of(context).textTheme.labelLarge,
              ),
              if (currentReview.correctedValue != null)
                Text(
                  "Corrected value: "
                  "${_formatCorrection(currentReview.correctedValue!)}",
                ),
              if (currentReview.note != null &&
                  currentReview.note!.trim().isNotEmpty)
                Text("Note: ${currentReview.note}"),
            ],
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (onAccept != null)
                  OutlinedButton.icon(
                    onPressed: busy ? null : onAccept,
                    icon: const Icon(Icons.check),
                    label: const Text("Accept"),
                  ),
                if (onCorrect != null)
                  FilledButton.tonalIcon(
                    onPressed: busy ? null : onCorrect,
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text("Correct"),
                  ),
                OutlinedButton.icon(
                  onPressed: busy ? null : onRecheck,
                  icon: const Icon(Icons.refresh),
                  label: const Text("Recheck"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  static String _declarationLabel(String value) {
    return switch (value) {
      "mrp" => "MRP",
      "net_quantity" => "Net quantity",
      _ => value,
    };
  }

  static String _decisionLabel(String value) {
    return switch (value) {
      "accepted" => "Accepted",
      "corrected" => "Corrected",
      "recheck_required" => "Recheck required",
      _ => value,
    };
  }

  static String _formatCorrection(Map<String, Object?> value) {
    if (value.containsKey("currency") && value.containsKey("amount")) {
      return "${value["currency"]} ${value["amount"]}";
    }
    if (value.containsKey("value") && value.containsKey("unit")) {
      return "${value["value"]} ${value["unit"]}";
    }
    return value.toString();
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final label = switch (status) {
      "pass" => "Preliminary pass",
      "manual_verification_required" => "Manual verification required",
      "potential_non_compliance" => "Potential non-compliance",
      "indeterminate" => "Indeterminate",
      "not_applicable" => "Not applicable",
      "not_evaluated" => "Not evaluated",
      _ => status,
    };
    return Chip(label: Text(label));
  }
}

class _CorrectionDraft {
  const _CorrectionDraft({
    required this.value,
    required this.note,
  });

  final Map<String, Object?> value;
  final String note;
}

class _CorrectionDialog extends StatefulWidget {
  const _CorrectionDialog({required this.result});

  final OfficerRuleResult result;

  @override
  State<_CorrectionDialog> createState() => _CorrectionDialogState();
}

class _CorrectionDialogState extends State<_CorrectionDialog> {
  String _numericValue = "";
  String _unit = "g";
  String _note = "";
  String? _error;

  void _submit() {
    final parsed = double.tryParse(_numericValue.trim());
    if (parsed == null || parsed <= 0) {
      setState(() => _error = "Enter a positive numeric value.");
      return;
    }
    if (_note.trim().isEmpty) {
      setState(() => _error = "An Officer note is required.");
      return;
    }

    final value = widget.result.declarationType == "mrp"
        ? <String, Object?>{
            "currency": "INR",
            "amount": _numericValue.trim(),
          }
        : <String, Object?>{
            "value": _numericValue.trim(),
            "unit": _unit,
          };

    Navigator.pop(
      context,
      _CorrectionDraft(
        value: value,
        note: _note.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isMrp = widget.result.declarationType == "mrp";
    return AlertDialog(
      title: Text(isMrp ? "Correct MRP" : "Correct net quantity"),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              autofocus: true,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: isMrp ? "Amount (INR)" : "Quantity",
                border: const OutlineInputBorder(),
              ),
              onChanged: (value) => _numericValue = value,
            ),
            if (!isMrp) ...[
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _unit,
                decoration: const InputDecoration(
                  labelText: "Unit",
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: "g", child: Text("g")),
                  DropdownMenuItem(value: "kg", child: Text("kg")),
                  DropdownMenuItem(value: "ml", child: Text("ml")),
                  DropdownMenuItem(value: "l", child: Text("L")),
                ],
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _unit = value);
                  }
                },
              ),
            ],
            const SizedBox(height: 12),
            TextField(
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: "Officer note",
                border: OutlineInputBorder(),
              ),
              onChanged: (value) => _note = value,
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(
                _error!,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text("Cancel"),
        ),
        FilledButton(
          onPressed: _submit,
          child: const Text("Save correction"),
        ),
      ],
    );
  }
}
