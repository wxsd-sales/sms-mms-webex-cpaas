# Webex Webhook Setup

<!-- step by step guide on creating a messages and attachmentAction created webhook from webex to the inbound webhook flow url created in the previous steps using the webex bot token. Leverage the webex webhook manager web tool to create these webhooks and uses its convient space lookup feature to filter the webhook notifications by their roomId. Preventing the bot from receiving noitifaction from other group or 1:1 chat -->

The final step is registering two Webex webhooks - one for `messages created` and one for `attachmentAction created` - scoped to the space's Room ID, targeting the Webhook Inbound flow URL. This guide uses the [Webex Webhook Manager](https://wxsd-sales.github.io/webex-webhook-manager/) web tool, which provides a convenient space lookup to fill in the `roomId` filter for you (so the bot only receives notifications for this one space, not any other group or 1:1 spaces it may also be a member of).

## Prerequisites

- The Bot's Access Token from [1. Webex Bot Setup](../1-webex-bot-setup/README.md)
- The Room ID from [2. Webex Space Setup](../2-webex-space-setup/README.md)
- The Webhook Inbound flow URL from [4. Webex Connect Flows](../4-webex-connect-flows/README.md)

## Steps

1. Open the [Webex Webhook Manager](https://wxsd-sales.github.io/webex-webhook-manager/) tool and authenticate using the Bot Access Token from step 1.

   ![Webhook Manager authentication](screenshots/01-webhook-manager-auth.png)

2. Use the tool's **space lookup** feature to search for and select the space created in [2. Webex Space Setup](../2-webex-space-setup/README.md). This automatically fills in the `roomId` filter, ensuring the bot only receives webhook notifications for this space.

   ![Space lookup](screenshots/02-space-lookup.png)

3. Create the first webhook:
   - **Resource:** `messages`
   - **Event:** `created`
   - **Filter:** `roomId=<space Room ID>`
   - **Target URL:** the Webhook Inbound flow URL from [4. Webex Connect Flows](../4-webex-connect-flows/README.md)

   ![Create messages webhook](screenshots/03-create-webhook-messages.png)

4. Create the second webhook:
   - **Resource:** `attachmentAction`
   - **Event:** `created`
   - **Filter:** `roomId=<space Room ID>`
   - **Target URL:** the same Webhook Inbound flow URL

   ![Create attachmentAction webhook](screenshots/04-create-webhook-attachmentaction.png)

5. Confirm both webhooks show as **Active** in the tool.
6. **Test end-to-end:**
   - Send a test SMS/MMS to your 10DLC number and confirm it appears as a new thread in the Webex Space.
   - Reply within that thread as an internal staff member.
   - Confirm the reply is delivered back to the test device via SMS/MMS.

This completes the setup - see the root [README](../README.md) for the full solution overview, flow diagram, and sequence diagram.
