# Webex Connect Flows

<!-- step by step guide on importing the attached flows into the webex connect service and configuring them by specifying the roomId of the webex space and assigning an SMS and MMS number to the inbound SMS and MMS flows along with the configuring the webex messaging inbound webex flow payload and capturing the created inbound webhook url for use in the next test. Flows include "SMS Inbound" "MMS Inbound" "Webhook Inbound" and "Relay Flow"-->

This solution is made up of four Webex Connect flows, exported as JSON under [flows/](flows/). Import them into the service created in [3. Webex Connect Service Setup](../3-webex-connect-service/README.md), then configure each one as described below.

> The files in [flows/](flows/) are placeholders. Replace them with the real exports from Flow Studio (**Flow > Export**) once they're finalized.

| Flow | Purpose |
|---|---|
| **SMS Inbound** | Triggered by an inbound SMS on the assigned number. Posts the message into the Webex Space as a new/existing thread via the Webex Messaging API. |
| **MMS Inbound** | Same as SMS Inbound, but for MMS - also maps any media attachment(s) into the Webex message. |
| **Webhook Inbound** | Public HTTPS endpoint that receives Webex `messages:created` and `attachmentAction:created` webhook events when a staff member replies in the thread. |
| **Relay Flow** | Invoked by Webhook Inbound. Resolves the external participant's phone number for the thread and sends the staff reply back out as an SMS/MMS. |

## Prerequisites

- The service created in [3. Webex Connect Service Setup](../3-webex-connect-service/README.md), with your SMS/MMS number assigned
- The bot's Access Token from [1. Webex Bot Setup](../1-webex-bot-setup/README.md)
- The Room ID from [2. Webex Space Setup](../2-webex-space-setup/README.md)

## Steps

1. Open the service in Webex Connect and go to **Flow Studio > Flows > Import Flow**.

   ![Import flow](screenshots/01-import-flow.png)

2. Import each JSON file from [flows/](flows/): `sms-inbound.flow.json`, `mms-inbound.flow.json`, `webhook-inbound.flow.json`, `relay-flow.flow.json`.

3. **Configure SMS Inbound:**
   - Open the SMS trigger node and assign your inbound SMS 10DLC number from [3. Webex Connect Service Setup](../3-webex-connect-service/README.md).
   - Open the "Post to Webex" API node and set:
     - `roomId` to the Room ID from [2. Webex Space Setup](../2-webex-space-setup/README.md)
     - `Authorization` header to `Bearer <Bot Access Token>` from [1. Webex Bot Setup](../1-webex-bot-setup/README.md)
   - Include the external participant's phone number in the outgoing message (text or metadata) so the reply can be matched back to it later.

   ![SMS Inbound configuration](screenshots/02-sms-inbound-config.png)

4. **Configure MMS Inbound:** repeat the same configuration as SMS Inbound, additionally mapping the inbound MMS media URL(s) into the Webex message's `files` field.

5. **Configure Webhook Inbound:**
   - Publish/activate the flow once to generate its public webhook URL.
   - Copy the URL - it is required in [5. Webex Webhook Setup](../5-webex-webhook-setup/README.md).

     ![Webhook Inbound URL](screenshots/03-webhook-inbound-url.png)

   - Configure the flow to parse the incoming Webex payload (`resource`, `event`, `data.id`), then call `GET /messages/{id}` on the Webex Messaging API (using the Bot token) to retrieve the full message content, since Webex webhook payloads do not include the message body.
   - Wire the flow to call the Relay Flow once the message content has been retrieved.

6. **Configure Relay Flow:**
   - Look up the external participant's phone number associated with the thread (`parentId`), using whatever mapping/data store the Inbound flows populated in steps 3-4.
   - Use the SMS/MMS Send node to deliver the reply text (and any attachments, for `attachmentAction` events) back to the external participant's number.

   ![Relay Flow configuration](screenshots/04-relay-flow-config.png)

7. Publish/activate all four flows.

## Next Step

Continue to [5. Webex Webhook Setup](../5-webex-webhook-setup/README.md).
