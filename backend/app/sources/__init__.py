from app.sources.banxico import BanxicoAdapter
from app.sources.bcb import BcbAdapter
from app.sources.boc import BocAdapter
from app.sources.ecb import EcbAdapter
from app.sources.ecos import EcosAdapter
from app.sources.evds import EvdsAdapter
from app.sources.fred import FredAdapter
from app.sources.imf import ImfAdapter
from app.sources.worldbank import WorldBankAdapter
from app.sources.yfinance_source import YFinanceAdapter

# Singleton adapter instances, referenced by name from the registry's
# per-country/indicator source priority chains.
ADAPTERS = {
    "fred": FredAdapter(),
    "ecb": EcbAdapter(),
    "boc": BocAdapter(),
    "bcb": BcbAdapter(),
    "banxico": BanxicoAdapter(),
    "ecos": EcosAdapter(),
    "evds": EvdsAdapter(),
    "imf": ImfAdapter(),
    "worldbank": WorldBankAdapter(),
    "yfinance": YFinanceAdapter(),
}
