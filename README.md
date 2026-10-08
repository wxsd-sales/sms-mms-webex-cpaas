# SMS MMS Webex CPaas

This is an example SMS/MMS to Webex solution which shows how to leverage a Webex Messaging Space and Threaded messages to enable members fo the Webex Space to engage in two way conversations with external participants.

<picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/introduction-flow-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/introduction-flow-light.svg">
    <img alt="Animated introduction to the SMS/MMS and Webex message flow between external participants and internal staff" src="images/introduction-flow-light.svg" width="90%">
</picture>



## Overview

Leveraging Webex Coonect Communication as a Service (CPaas) service flows, this solution acts as a message broker between an organisations internal Webex users and external participants which uses SMS/MMS.

- Inbound SMS/MMS Chat Sessions: New sessions trigger a new thread. Existing sessions have inbound messages appending to thread.
- Adaptive Card Bard Replies
- Automatic and Manual based session termination


<picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/overview-flow-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/overview-flow-light.svg">
    <img alt="Animated overview of the inbound SMS/MMS and Webex flows" src="images/overview-flow-light.svg" width="90%">
</picture>

### Sequence Diagram

<details>

<summary>Show Sequence Diagram</summary>

```mermaid
sequenceDiagram
    participant EP as External Participant
    participant WCF as Webex Connect Flows
    participant WMA as Webex Messaging API
    participant Space as Webex Space Thread
    participant Staff as Internal Staff
    participant WH as Webex Webhook

    EP->>WCF: SMS/MMS message
    WCF->>WMA: POST /messages (roomId, parentId, text/files)
    WMA->>Space: Post message into thread
    Space-->>Staff: Notification in Webex Space
    Staff->>Space: Reply within the thread
    Space->>WH: messages:created / attachmentAction:created event
    WH->>WCF: POST event payload (Webhook Inbound flow)
    WCF->>WMA: GET /messages/{id} (fetch full content)
    WCF->>WCF: Relay Flow - map thread to external phone number
    WCF->>EP: SMS/MMS reply
```

</details>

## Setup

### Prerequisites & Dependencies:

- Webex Connect Tenant with Admin access
- Webex Connect 10DLC number with SMS and MMS support, provisioned on the Webex Connect tenant
- A Webex Account - User For:
    - Creating the Webex Bot
    - Creating the Webex Space which this solution uses
    - Adding the Webex Bot and Internal Staff users to the solutions Webex Space
- Internal staff who will respond to conversations must be members of the Webex App with access to the space

### Setup Steps:

Follow these steps in order - each one produces a value (token, room ID, or URL) used by a later step:

1. [Webex Bot Setup](1-webex-bot-setup/README.md) - create the bot used to post messages and authenticate webhooks
2. [Webex Space Setup](2-webex-space-setup/README.md) - create the space, add the bot & staff, capture the Room ID
3. [Webex Connect Service Setup](3-webex-connect-service/README.md) - create the Webex Connect service and assign your SMS/MMS number
4. [Webex Connect Flows](4-webex-connect-flows/README.md) - import & configure the SMS Inbound, MMS Inbound, Webhook Inbound and Relay flows
5. [Webex Webhook Setup](5-webex-webhook-setup/README.md) - create the Webex webhooks that notify the flows when staff reply

## Demo

\*For more demos & PoCs like this, check out our [Webex Labs site](https://collabtoolbox.cisco.com/webex-labs).

## License

All contents are licensed under the MIT license. Please see [license](LICENSE) for details.

## Disclaimer

Everything included is for demo and Proof of Concept purposes only. Use of the site is solely at your own risk. This site may contain links to third party content, which we do not warrant, endorse, or assume liability for. These demos are for Cisco Webex use cases, but are not Official Cisco Webex Branded demos.

## Questions

Please contact the WXSD team at [wxsd@external.cisco.com](mailto:wxsd@external.cisco.com?subject=sms-mms-webex-cpaas) for questions. Or, if you're a Cisco internal employee, reach out to us on the Webex App via our bot (globalexpert@webex.bot). In the "Engagement Type" field, choose the "API/SDK Proof of Concept Integration Development" option to make sure you reach our team.
