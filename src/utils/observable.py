"""Observable pattern implementation for MVVM architecture."""

from typing import Any, Callable, Dict, List


class Observable:
    """Base class for observable objects that can notify observers of property changes.

    This class implements the Observer pattern, allowing ViewModels to notify Views
    when their state changes. Views can register callbacks to be notified of specific
    property changes.

    Example:
        class MyViewModel(Observable):
            def __init__(self):
                super().__init__()
                self._count = 0

            def increment(self):
                self.set_and_notify("count", self._count + 1)

        # In the view:
        viewmodel = MyViewModel()
        viewmodel.observe("count", lambda value: print(f"Count: {value}"))
        viewmodel.increment()  # Prints: Count: 1
    """

    def __init__(self):
        """Initialize the observable with an empty observer registry."""
        self._observers: Dict[str, List[Callable[[Any], None]]] = {}

    def observe(self, property_name: str, callback: Callable[[Any], None]) -> None:
        """Register a callback to be notified when a property changes.

        Args:
            property_name: Name of the property to observe
            callback: Function to call when the property changes.
                     Receives the new value as an argument.
        """
        if property_name not in self._observers:
            self._observers[property_name] = []

        self._observers[property_name].append(callback)

    def unobserve(self, property_name: str, callback: Callable[[Any], None]) -> None:
        """Unregister a callback for a property.

        Args:
            property_name: Name of the property
            callback: The callback to remove
        """
        if property_name in self._observers:
            try:
                self._observers[property_name].remove(callback)
            except ValueError:
                pass  # Callback wasn't registered

    def notify(self, property_name: str, value: Any) -> None:
        """Notify all observers of a property that it has changed.

        Args:
            property_name: Name of the property that changed
            value: New value of the property
        """
        if property_name in self._observers:
            for callback in self._observers[property_name]:
                try:
                    callback(value)
                except Exception as e:
                    # Log but don't let observer errors break the notification chain
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Error in observer callback for '{property_name}': {e}",
                        exc_info=True
                    )

    def set_and_notify(self, property_name: str, value: Any) -> None:
        """Set a property value and notify observers.

        This is a convenience method that combines setting a private property
        and notifying observers in one call.

        Args:
            property_name: Name of the property (without leading underscore)
            value: New value to set

        Note:
            This assumes the actual property is stored with a leading underscore.
            For example, if property_name is "count", it will set self._count.
        """
        private_name = f"_{property_name}"
        old_value = getattr(self, private_name, None)

        # Only notify if value actually changed
        if old_value != value:
            setattr(self, private_name, value)
            self.notify(property_name, value)

    def clear_observers(self, property_name: str = None) -> None:
        """Clear all observers for a property, or all observers if no property specified.

        Args:
            property_name: Name of the property to clear observers for,
                          or None to clear all observers
        """
        if property_name is None:
            self._observers.clear()
        elif property_name in self._observers:
            self._observers[property_name].clear()
