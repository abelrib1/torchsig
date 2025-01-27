from torchsig.utils.types import SignalData, SignalDescription
from torchsig.datasets.modulations import ModulationsDataset
from torchsig.transforms.transforms import NoTransform
from torchsig.datasets import conf
from copy import deepcopy
from pathlib import Path
import numpy as np
import pickle
import lmdb


class Sig53:
    """The Official Sig53 dataset

    Args:
        root (string):
            Root directory of dataset. A folder will be created for the
            requested version of the dataset, an mdb file inside contains the
            data and labels.

        train (bool, optional):
            If True, constructs the corresponding training set, otherwise
            constructs the corresponding val set

        impaired (bool, optional):
            If True, will construct the impaired version of the dataset, with
            data passed through a seeded channel model

        eb_no (bool, optional):
            If True, will define SNR as Eb/No; If False, will define SNR as Es/No

        transform (callable, optional):
            A function/transform that takes in a complex64 ndarray and returns
            a transformed version

        target_transform (callable, optional):
            A function/transform that takes in the target class (int) and
            returns a transformed version

        use_signal_data (bool, optional):
            If True, data will be converted to SignalData objects as read in.
            Default: False.

    """

    _idx_to_name_dict = dict(zip(range(53), ModulationsDataset.default_classes))
    _name_to_idx_dict = dict(zip(ModulationsDataset.default_classes, range(53)))

    @staticmethod
    def convert_idx_to_name(idx: int) -> str:
        return Sig53._idx_to_name_dict.get(idx, "unknown")

    @staticmethod
    def convert_name_to_idx(name: str) -> int:
        return Sig53._name_to_idx_dict.get(name, -1)

    def __init__(
        self,
        root: str,
        train: bool = True,
        impaired: bool = True,
        eb_no: bool = False,
        transform: callable = None,
        target_transform: callable = None,
        use_signal_data: bool = False,
    ):
        self.root = Path(root)
        self.train = train
        self.impaired = impaired
        self.eb_no = eb_no
        self.use_signal_data = use_signal_data

        self.T = transform if transform else NoTransform()
        self.TT = target_transform if target_transform else NoTransform()

        cfg: conf.Sig53Config = (
            "Sig53"
            + ("Impaired" if impaired else "Clean")
            + ("EbNo" if (impaired and eb_no) else "")
            + ("Train" if train else "Val")
            + "Config"
        )

        cfg = getattr(conf, cfg)()

        self.path = self.root / cfg.name
        self.env = lmdb.Environment(
            str(self.path).encode(), map_size=int(1e12), max_dbs=2, lock=False
        )
        self.data_db = self.env.open_db(b"data")
        self.label_db = self.env.open_db(b"label")
        with self.env.begin(db=self.data_db) as data_txn:
            self.length = data_txn.stat()["entries"]

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, idx: int) -> tuple:
        encoded_idx = pickle.dumps(idx)
        with self.env.begin(db=self.data_db) as data_txn:
            iq_data = pickle.loads(data_txn.get(encoded_idx)).numpy()

        with self.env.begin(db=self.label_db) as label_txn:
            mod, snr = pickle.loads(label_txn.get(encoded_idx))

        mod = int(mod.numpy())
        if self.use_signal_data:
            signal_desc = SignalDescription(
                class_name=self._idx_to_name_dict[mod],
                class_index=mod,
                snr=snr,
            )
            data: SignalData = SignalData(
                data=deepcopy(iq_data.tobytes()),
                item_type=np.dtype(np.float64),
                data_type=np.dtype(np.complex128),
                signal_description=[signal_desc],
            )
            data = self.T(data)
            target = self.TT(data.signal_description)
            data = data.iq_data
            return data, target

        data = self.T(iq_data)
        target = (self.TT(mod), snr)

        return data, target
