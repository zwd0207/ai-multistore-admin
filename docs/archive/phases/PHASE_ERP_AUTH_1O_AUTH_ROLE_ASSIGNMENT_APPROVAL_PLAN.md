# Phase ERP-Auth-1O: Auth role assignment approval plan

## Purpose

Plan the future approval flow for assigning ERP roles to users and stores.

## Required Future Gate

A role assignment write phase must require:

- real target user exists
- target store exists
- target role exists
- no duplicate active membership
- admin or owner approval
- assignment reason
- database backup
- audit evidence
- rollback/revoke instructions
- post-write readback
- sensitive scan

## Current Boundary

The auth foundation tables and permission metadata exist, but production login, user creation, role assignment UI, route-level authorization, and real store memberships remain closed.

