# Phase ERP-Auth-1H: Runtime permission API production-auth boundary plan

## Purpose

Define the boundary between the current mock permission API and a future production authentication and authorization system.

This phase is planning-only.

## Current State

The current permission API is useful for local UI visibility and approval planning, but it is not a production auth system.

It does not create:

- real login sessions
- password flows
- user tables
- role assignment tables
- store membership tables
- JWT/session middleware
- production route dependencies

## Future Production Auth Requirements

A production version should add, in separately approved phases:

- user and role schema
- store membership schema
- login/session boundary
- password or SSO policy
- route-level permission dependency
- audit rows for permission-sensitive actions
- admin UI for assigning roles and stores
- tests for cross-store isolation
- backup and rollback plans before schema migration

Until those exist, the mock permission API must not be described as final access control.
