# Account deletion and password reset

## Deleting an account

A superuser administrator can open **Users**, select an account and choose
**Delete**, or select several accounts and use **Delete selected users**.
Review the confirmation page and confirm to apply the deletion.

Deleting an account permanently removes all reservations linked to it as the
requester, reviewer or person who cancelled the reservation. This includes
pending, approved, rejected, cancelled and archived reservations. Deleting an
administrator also removes reservations they reviewed/cancelled for other users;
the confirmation lists those records. Saved sign-in sessions and history about
the deleted accounts and reservations are removed too.

An approved reservation no longer blocks its room after deletion. Availability
is recalculated from the remaining timetable and reservations on the next refresh.
Rooms, buildings, courses, timetable entries and other accounts are not deleted.
The change applies when an administrator confirms deletion; the migration itself
does not remove any existing data. Standalone reservation deletion remains
unavailable; the normal reservation actions are Approve, Reject and Cancel.

## Resetting a password

Only superuser administrators can reset an account password:

1. Open **Users** and find the account by email or name.
2. Click **Reset password** beside the account, or open it and use the same link.
3. Enter **New password** and **Confirm new password**, then click **Reset password**.
4. Give the password to the account holder privately. No email service is needed.

The old password is not required. The existing password rules still apply:
at least eight characters, not too similar to account details, not a commonly
used password, and not entirely numeric. Matching passwords are required.
There are no new requirements for uppercase letters, symbols or periodic resets.

The reset invalidates the account's old password and existing sessions. It does
not activate an unapproved lecturer, change roles or grant administrator access.
If an administrator changes their own password, Django keeps that browser signed
in with the new password and invalidates their other sessions. The password is
hashed, never stored or written to admin history as plaintext. Django history
records that a password changed without recording its value.

Student and lecturer login pages direct users who forgot their password to an
administrator. There is no public email-reset endpoint or paid email dependency.
