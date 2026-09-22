# Phase 2 — Capture and Evidence Storage

Status: In progress

## Goal

Accept real package images as inspection evidence while preserving the original bytes and keeping access tied to the inspection authorization model.

## First slice — original evidence ingestion

This slice implements:

- authenticated image upload to an officer-owned draft inspection;
- multiple capture view types;
- JPEG/PNG/WebP verification using decoded image content;
- generated storage keys rather than user-controlled filesystem paths;
- SHA-256 checksum;
- width/height, MIME type and size metadata;
- protected capture listing;
- protected byte-for-byte original retrieval;
- capture-upload audit event;
- local filesystem storage adapter behind a replaceable dependency.

## Explicitly not implemented yet

- blur/glare/exposure scoring;
- orientation/perspective correction;
- label-region detection;
- OCR;
- declaration extraction;
- font-size measurement;
- compliance decisions.

Those belong to later Phase 2/3 slices.

## Evidence rule

The original uploaded image is immutable evidence. Any later preprocessing must create a derivative and must not overwrite the original storage object or checksum.

## Storage rule

Local filesystem storage is the development/prototype baseline. The API uses generated storage keys and a storage dependency so an object-storage adapter can be introduced later without changing inspection/capture semantics.

## Exit condition for this slice

A real supported image can be uploaded, stored, listed and retrieved securely, and its retrieved bytes match the submitted bytes and stored SHA-256 checksum. Invalid, unsupported, oversized or unauthorized uploads must fail explicitly.
