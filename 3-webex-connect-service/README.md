# Webex Connect Service

<!-- step by step guide on creating a webex connect service for this solution this is short guide-->

A Webex Connect **Service** is the container that holds the flows, channel numbers, and configuration for this solution. This is a short guide since most of the work happens in [4. Webex Connect Flows](../4-webex-connect-flows/README.md).

## Prerequisites

- Webex Connect tenant with Admin access
- A Webex Connect 10DLC number with SMS and MMS support provisioned on the tenant

## Steps

1. Log in to your Webex Connect tenant admin portal.
2. Navigate to **Services** (or **Apps**) and click **Create Service**.

   ![Create service](screenshots/01-create-service.png)

3. Give the service a name, for example `SMS-MMS-Webex-Bridge`, and select the flow-based service type.
4. Click **Create** to provision the service.
5. Open the new service and go to **Numbers / Channels**, then assign your provisioned SMS and MMS 10DLC number(s) to this service.

   ![Assign numbers](screenshots/02-assign-numbers.png)

6. If your organization requires it, note the service's **Service ID / API Key** from the service settings page - not required for the basic flow-only integration in this guide, but useful if you extend the solution to call the Connect API directly.

## Next Step

Continue to [4. Webex Connect Flows](../4-webex-connect-flows/README.md).
