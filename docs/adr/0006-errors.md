# 0006. Errors: ApiError and stable codes
Status: Accepted
Date: 2026-10-21

## Context
Decided at the start of the project: one error contract. A client branches on a code, never on a message.

## Decision
- Every HTTP error is an `ApiError` built by the factories of `shelfdrop/http/errors/errors.py`, through the `errors.py` of its feature.
- Every error body is `{"code", "detail", "data"}`; `ErrorCode` is the single list of codes, each member commented with its status, meaning and `data`.
- A `422` never repeats the values sent; a `500` never carries the exception, which stays in the logs.

## Rejected alternatives
- `HTTPException` with a free message: no stable code.

## Consequences
- A new error adds a member to `ErrorCode` and a factory to the `errors.py` of its feature.
