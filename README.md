# Rocket.Chat.UnifiedPush.Gateway
Gateway for unlimited notifications with Rocket.Chat and UnifiedPush

## to setup:
1) admin in Rocket.chat registers webhook in workspace -> Integrations -> Outgoing for ['DM', 'Channels', 'Private groups'] to http://localhost:5001/rocket-webhook-direct
2) run redis and ntfy or comparable as desired ( REDIS for user -> topic, NTFY for gateway)
3) run flask as desired


## TODO:
[ ] add in VAPID
