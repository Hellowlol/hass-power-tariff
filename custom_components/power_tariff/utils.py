import logging

_LOGGER = logging.getLogger(__name__)


def get_entity_object(hass, entity_id):
    """you are not allowed to interact directly with entity objects 🤷"""
    domain = entity_id.split('.')[0]
    try:
        for ent in hass.data[domain].entities:
            if ent.entity_id == entity_id:
                _LOGGER.debug("Found it, %r", ent)
                return ent
    except Exception as e:
        _LOGGER.exception("Fail to get the entity using %s", entity_id)

    return None
