import time

class ServiceDispatcher:
    """Handles dispatching of Home Assistant services based on UI actions."""
    
    def __init__(self, ha_client):
        self.ha_client = ha_client
        self._last_click_time: dict[str, float] = {}  # entity_id -> timestamp
        self._click_cooldown = 0.5
        
    async def handle_button_click(self, config: dict):
        """Process a standard button click."""
        btn_type = config.get('type', 'switch')
        entity_id = config.get('entity_id', '')
        
        if not entity_id: return
        
        # Debounce
        current_time = time.time()
        last_time = self._last_click_time.get(entity_id, 0)
        if not config.get('skip_debounce', False) and (current_time - last_time < self._click_cooldown):
            return
        self._last_click_time[entity_id] = current_time
        
        # Check for explicit service call (e.g. from Dimmer)
        if config.get('service'):
            full_service = config['service']
            if '.' in full_service:
                domain, service = full_service.split('.', 1)
            else:
                domain, service = 'homeassistant', full_service
            
            data = config.get('service_data', {})
            await self.ha_client.call_service(domain, service, entity_id, data)
            return

        domain = 'homeassistant'
        service = 'toggle'
        data = {}
        
        if btn_type == 'curtain':
            domain = 'cover'
            service = 'toggle'
        elif btn_type == 'media_player':
            domain = 'media_player'
            service = config.get('action', 'media_play_pause')
        elif btn_type == 'script':
            domain = 'script'
            service = 'turn_on'
        elif btn_type == 'automation':
            domain = 'automation'
            service = 'trigger' if config.get('action') == 'trigger' else 'toggle'
        elif btn_type == 'scene':
            domain = 'scene'
            service = 'turn_on'
        elif btn_type == 'lock':
            domain = 'lock'
            # Check cached state/toggle
            state = await self.ha_client.get_state(entity_id)
            current = state.get('state') if state else 'locked'
            service = 'unlock' if current == 'locked' else 'lock'
            
        await self.ha_client.call_service(domain, service, entity_id, data)

    async def handle_volume_scroll(self, entity_id: str, volume: float):
        """Handle mouse wheel scroll for volume adjustment."""
        await self.ha_client.call_service(
            'media_player', 'volume_set', entity_id, {'volume_level': volume}
        )

    async def handle_media_command(self, entity_id: str, command: str):
        """Handle specific media playback commands."""
        await self.ha_client.call_service(
            'media_player', command, entity_id
        )
