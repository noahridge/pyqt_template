"""Optional MVVM layer.

ViewModels for screens with real presentation logic. Entirely opt-in — delete
this package (and the Control page that uses it) if your screens are simple
read-outs that bind to the model directly.
"""

from hmi.views.viewmodels.base import ViewModel, bind
from hmi.views.viewmodels.pump_control import PumpControlViewModel

__all__ = ["ViewModel", "bind", "PumpControlViewModel"]
