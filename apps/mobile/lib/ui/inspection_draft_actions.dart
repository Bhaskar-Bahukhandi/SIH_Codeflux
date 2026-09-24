import "package:flutter/material.dart";

class InspectionDraftEditResult {
  const InspectionDraftEditResult({
    required this.productName,
    this.productIdentifier,
  });

  final String productName;
  final String? productIdentifier;
}

Future<InspectionDraftEditResult?> showInspectionEditDialog(
  BuildContext context, {
  required String productName,
  String? productIdentifier,
}) {
  return showDialog<InspectionDraftEditResult>(
    context: context,
    builder: (_) => _InspectionEditDialog(
      productName: productName,
      productIdentifier: productIdentifier,
    ),
  );
}

Future<bool> confirmDiscardInspection(
  BuildContext context, {
  required String productName,
}) async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: const Text("Discard inspection?"),
      content: Text(
        'Discard "$productName"? This removes it from the Officer workspace. '
        "Draft-only server cleanup will be queued when needed.",
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
  return confirmed == true;
}

class _InspectionEditDialog extends StatefulWidget {
  const _InspectionEditDialog({
    required this.productName,
    this.productIdentifier,
  });

  final String productName;
  final String? productIdentifier;

  @override
  State<_InspectionEditDialog> createState() => _InspectionEditDialogState();
}

class _InspectionEditDialogState extends State<_InspectionEditDialog> {
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
    final name = _productController.text.trim();
    final identifier = _identifierController.text.trim();
    Navigator.pop(
      context,
      InspectionDraftEditResult(
        productName: name,
        productIdentifier: identifier.isEmpty ? null : identifier,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text("Edit inspection details"),
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
                decoration: const InputDecoration(labelText: "Product name"),
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
