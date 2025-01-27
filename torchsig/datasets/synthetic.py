import torch
import pickle
import itertools
import numpy as np
from copy import deepcopy
from scipy import signal as sp
from collections import OrderedDict
from torch.utils.data import ConcatDataset
from typing import Tuple, Any, List, Union, Optional
from torchsig.utils.dataset import SignalDataset
from torchsig.utils.types import SignalData, SignalDescription
from torchsig.transforms.functional import IntParameter, FloatParameter
from torchsig.datasets import estimate_filter_length


def torchsig_convolve(
    signal: np.ndarray, taps: np.ndarray, gpu: bool = False
) -> np.ndarray:
    return sp.convolve(signal, taps, "same")
    # This will run into issues is signal is smaller than taps
    # torch_signal = torch.from_numpy(signal.astype(np.complex128)).reshape(1, -1)
    # torch_taps = torch.flip(
    #     torch.from_numpy(taps.astype(np.complex128)).reshape(1, 1, -1), dims=(2,)
    # )
    # if gpu:
    #     result = torch.nn.functional.conv1d(
    #         torch_signal.cuda(), torch_taps.cuda(), padding=torch_signal.shape[0] - 1
    #     )
    #     return result.cpu().numpy()[0]

    # result = torch.nn.functional.conv1d(
    #     torch_signal, torch_taps, padding=torch_signal.shape[0] - 1
    # )
    # return result.numpy()[0]


def remove_corners(const):
    spacing = 2.0 / (np.sqrt(len(const)) - 1)
    cutoff = spacing * (np.sqrt(len(const)) / 6 - 0.5)
    return [
        p
        for p in const
        if np.abs(np.real(p)) < 1.0 - cutoff or np.abs(np.imag(p)) < 1.0 - cutoff
    ]


default_const_map = OrderedDict(
    {
        "ook": np.add(*map(np.ravel, np.meshgrid(np.linspace(0, 1, 2), 0j))),
        "bpsk": np.add(*map(np.ravel, np.meshgrid(np.linspace(-1, 1, 2), 0j))),
        "4pam": np.add(*map(np.ravel, np.meshgrid(np.linspace(0, 1, 4), 0j))),
        "4ask": np.add(*map(np.ravel, np.meshgrid(np.linspace(-1, 1, 4), 0j))),
        "qpsk": np.add(
            *map(
                np.ravel, np.meshgrid(np.linspace(-1, 1, 2), 1j * np.linspace(-1, 1, 2))
            )
        ),
        "8pam": np.add(*map(np.ravel, np.meshgrid(np.linspace(0, 1, 8), 0j))),
        "8ask": np.add(*map(np.ravel, np.meshgrid(np.linspace(-1, 1, 8), 0j))),
        "8psk": np.exp(2j * np.pi * np.linspace(0, 7, 8) / 8.0),
        "16qam": np.add(
            *map(
                np.ravel, np.meshgrid(np.linspace(-1, 1, 4), 1j * np.linspace(-1, 1, 4))
            )
        ),
        "16pam": np.add(*map(np.ravel, np.meshgrid(np.linspace(0, 1, 16), 0j))),
        "16ask": np.add(*map(np.ravel, np.meshgrid(np.linspace(-1, 1, 16), 0j))),
        "16psk": np.exp(2j * np.pi * np.linspace(0, 15, 16) / 16.0),
        "32qam": np.add(
            *map(
                np.ravel, np.meshgrid(np.linspace(-1, 1, 4), 1j * np.linspace(-1, 1, 8))
            )
        ),
        "32qam_cross": remove_corners(
            np.add(
                *map(
                    np.ravel,
                    np.meshgrid(np.linspace(-1, 1, 6), 1j * np.linspace(-1, 1, 6)),
                )
            )
        ),
        "32pam": np.add(*map(np.ravel, np.meshgrid(np.linspace(0, 1, 32), 0j))),
        "32ask": np.add(*map(np.ravel, np.meshgrid(np.linspace(-1, 1, 32), 0j))),
        "32psk": np.exp(2j * np.pi * np.linspace(0, 31, 32) / 32.0),
        "64qam": np.add(
            *map(
                np.ravel, np.meshgrid(np.linspace(-1, 1, 8), 1j * np.linspace(-1, 1, 8))
            )
        ),
        "64pam": np.add(*map(np.ravel, np.meshgrid(np.linspace(0, 1, 64), 0j))),
        "64ask": np.add(*map(np.ravel, np.meshgrid(np.linspace(-1, 1, 64), 0j))),
        "64psk": np.exp(2j * np.pi * np.linspace(0, 63, 64) / 64.0),
        "128qam_cross": remove_corners(
            np.add(
                *map(
                    np.ravel,
                    np.meshgrid(np.linspace(-1, 1, 12), 1j * np.linspace(-1, 1, 12)),
                )
            )
        ),
        "256qam": np.add(
            *map(
                np.ravel,
                np.meshgrid(np.linspace(-1, 1, 16), 1j * np.linspace(-1, 1, 16)),
            )
        ),
        "512qam_cross": remove_corners(
            np.add(
                *map(
                    np.ravel,
                    np.meshgrid(np.linspace(-1, 1, 24), 1j * np.linspace(-1, 1, 24)),
                )
            )
        ),
        "1024qam": np.add(
            *map(
                np.ravel,
                np.meshgrid(np.linspace(-1, 1, 32), 1j * np.linspace(-1, 1, 32)),
            )
        ),
    }
)

# This is probably redundant.
freq_map = OrderedDict(
    {
        "2fsk": np.linspace(-1 + (1 / 2), 1 - (1 / 2), 2, endpoint=True),
        "2gfsk": np.linspace(-1 + (1 / 2), 1 - (1 / 2), 2, endpoint=True),
        "2msk": np.linspace(-1 + (1 / 2), 1 - (1 / 2), 2, endpoint=True),
        "2gmsk": np.linspace(-1 + (1 / 2), 1 - (1 / 2), 2, endpoint=True),
        "4fsk": np.linspace(-1 + (1 / 4), 1 - (1 / 4), 4, endpoint=True),
        "4gfsk": np.linspace(-1 + (1 / 4), 1 - (1 / 4), 4, endpoint=True),
        "4msk": np.linspace(-1 + (1 / 4), 1 - (1 / 4), 4, endpoint=True),
        "4gmsk": np.linspace(-1 + (1 / 4), 1 - (1 / 4), 4, endpoint=True),
        "8fsk": np.linspace(-1 + (1 / 8), 1 - (1 / 8), 8, endpoint=True),
        "8gfsk": np.linspace(-1 + (1 / 8), 1 - (1 / 8), 8, endpoint=True),
        "8msk": np.linspace(-1 + (1 / 8), 1 - (1 / 8), 8, endpoint=True),
        "8gmsk": np.linspace(-1 + (1 / 8), 1 - (1 / 8), 8, endpoint=True),
        "16fsk": np.linspace(-1 + (1 / 16), 1 - (1 / 16), 16, endpoint=True),
        "16gfsk": np.linspace(-1 + (1 / 16), 1 - (1 / 16), 16, endpoint=True),
        "16msk": np.linspace(-1 + (1 / 16), 1 - (1 / 16), 16, endpoint=True),
        "16gmsk": np.linspace(-1 + (1 / 16), 1 - (1 / 16), 16, endpoint=True),
    }
)


class DigitalModulationDataset(ConcatDataset):
    """Digital Modulation Dataset

    Args:
        modulations (:obj:`list` or :obj:`tuple`):
            Sequence of strings representing the constellations that should be included.

        num_iq_samples (:obj:`int`):
            number of samples to read from each file in the database

        num_samples_per_class (:obj:`int`):
            number of samples to be kept for each class

        iq_samples_per_symbol (:obj:`Optional[int]`):
            number of IQ samples per symbol

        random_data (:obj:`bool`):
            whether the modulated binary utils should be random each time, or seeded by index

        random_pulse_shaping (:obj:`bool`):
            boolean to enable/disable randomized pulse shaping

        user_const_map (:obj:`Optional[OrderedDict]`):
            optional user-defined constellation map, defaults to Sig53 modulations

    """

    def __init__(
        self,
        modulations: Optional[Union[List, Tuple]] = ("bpsk", "2gfsk"),
        num_iq_samples: int = 100,
        num_samples_per_class: int = 100,
        iq_samples_per_symbol: Optional[int] = None,
        random_data: bool = False,
        random_pulse_shaping: bool = False,
        user_const_map: Optional[OrderedDict] = None,
        **kwargs,
    ):
        const_map = user_const_map if user_const_map else default_const_map
        modulations = (
            list(const_map.keys()) + list(freq_map.keys())
            if modulations is None
            else modulations
        )
        constellations = [
            m for m in map(str.lower, modulations) if m in const_map.keys()
        ]
        freqs = [m for m in map(str.lower, modulations) if m in freq_map.keys()]
        const_dataset = ConstellationDataset(
            constellations=constellations,
            num_iq_samples=num_iq_samples,
            num_samples_per_class=num_samples_per_class,
            iq_samples_per_symbol=2
            if iq_samples_per_symbol is None
            else iq_samples_per_symbol,
            random_data=random_data,
            random_pulse_shaping=random_pulse_shaping,
            **kwargs,
        )

        # FSK signals with the Gaussian pulse shaping filter are handled differently than without
        fsks = []
        gfsks = []
        for freq_mod in freqs:
            if "g" in freq_mod:
                gfsks.append(freq_mod)
            else:
                fsks.append(freq_mod)
        fsk_dataset = FSKDataset(
            modulations=fsks,
            num_iq_samples=num_iq_samples,
            num_samples_per_class=num_samples_per_class,
            iq_samples_per_symbol=8,
            random_data=random_data,
            random_pulse_shaping=random_pulse_shaping,
            **kwargs,
        )
        gfsks_dataset = FSKDataset(
            modulations=gfsks,
            num_iq_samples=num_iq_samples,
            num_samples_per_class=num_samples_per_class,
            iq_samples_per_symbol=8,
            random_data=random_data,
            random_pulse_shaping=random_pulse_shaping,
            **kwargs,
        )
        super(DigitalModulationDataset, self).__init__(
            [const_dataset, fsk_dataset, gfsks_dataset]
        )


class SyntheticDataset(SignalDataset):
    def __init__(self, **kwargs):
        super(SyntheticDataset, self).__init__(**kwargs)
        self.index = []

    def __getitem__(self, index: int) -> Tuple[SignalData, Any]:
        signal_description = self.index[index][-1]
        signal_data = SignalData(
            data=self._generate_samples(self.index[index]).tobytes(),
            item_type=np.dtype(np.float64),
            data_type=np.dtype(np.complex128),
            signal_description=signal_description,
        )

        if self.transform:
            signal_data = self.transform(signal_data)

        if self.target_transform:
            target = self.target_transform(signal_data.signal_description)
        else:
            target = signal_description

        return signal_data.iq_data, target

    def __len__(self) -> int:
        return len(self.index)

    def _generate_samples(self, item: Tuple) -> np.ndarray:
        raise NotImplementedError


class ConstellationDataset(SyntheticDataset):
    """Constellation Dataset

    Args:
        constellations (:obj:`list` or :obj:`tuple`):
            Sequence of strings representing the constellations that should be included.

        num_iq_samples (:obj:`int`):
            number of samples to read from each file in the database

        num_samples_per_class (:obj:`int`):
            number of samples to be kept for each class

        iq_samples_per_symbol (:obj:`int`):
            number of IQ samples per symbol

        pulse_shape_filter (:obj:`int`):
            Pulse shape filter to apply to the up-sampled symbols. Default is RRC spanning 11 symbols.

        random_data (:obj:`bool`):
            whether the modulated binary utils should be random each time, or seeded by index

        user_const_map (:obj:`bool`):
            user constellation dict

    """

    def __init__(
        self,
        constellations: Optional[Union[List, Tuple]] = ("bpsk", "qpsk"),
        num_iq_samples: int = 100,
        num_samples_per_class: int = 100,
        iq_samples_per_symbol: int = 2,
        pulse_shape_filter: bool = None,
        random_pulse_shaping: bool = False,
        random_data: bool = False,
        use_gpu: bool = False,
        user_const_map: bool = None,
        **kwargs,
    ):
        super(ConstellationDataset, self).__init__(**kwargs)
        self.const_map = default_const_map if user_const_map is None else user_const_map
        self.constellations = (
            list(self.const_map.keys()) if constellations is None else constellations
        )
        self.num_iq_samples = num_iq_samples
        self.iq_samples_per_symbol = iq_samples_per_symbol
        self.num_samples_per_class = num_samples_per_class
        self.random_pulse_shaping = random_pulse_shaping
        self.use_gpu = use_gpu

        num_constellations = len(self.constellations)
        total_num_samples = int(num_constellations * self.num_samples_per_class)

        if pulse_shape_filter is None:
            if self.random_pulse_shaping:
                alphas = np.random.uniform(0.15, 0.6, size=total_num_samples)
            else:
                alphas = np.ones(total_num_samples) * 0.35
        else:
            self.pulse_shape_filter = pulse_shape_filter

        self.random_data = random_data
        self.index = []

        for const_idx, const_name in enumerate(map(str.lower, self.constellations)):
            for idx in range(self.num_samples_per_class):
                signal_description = SignalDescription(
                    sample_rate=0,
                    bits_per_symbol=np.log2(len(self.const_map[const_name])),
                    samples_per_symbol=iq_samples_per_symbol,
                    class_name=const_name,
                    excess_bandwidth=alphas[
                        int(const_idx * self.num_samples_per_class + idx)
                    ],
                )
                self.index.append(
                    (
                        const_name,
                        const_idx * self.num_samples_per_class + idx,
                        signal_description,
                    )
                )

    def _generate_samples(self, item: Tuple) -> np.ndarray:
        class_name = item[0]
        index = item[1]
        signal_description = item[2]
        orig_state = np.random.get_state()
        if not self.random_data:
            np.random.seed(index)

        const = self.const_map[class_name] / np.mean(np.abs(self.const_map[class_name]))
        symbol_nums = np.random.randint(
            0, len(const), int(self.num_iq_samples / self.iq_samples_per_symbol)
        )
        symbols = const[symbol_nums]
        zero_padded = np.zeros(
            (self.iq_samples_per_symbol * len(symbols),), dtype=np.complex64
        )
        zero_padded[:: self.iq_samples_per_symbol] = symbols
        # excess bandwidth is defined in porportion to signal bandwidth, not sampling rate,
        # thus needs to be scaled by the samples per symbol
        pulse_shape_filter_length = estimate_filter_length(
            signal_description.excess_bandwidth / self.iq_samples_per_symbol
        )
        pulse_shape_filter_span = int(
            (pulse_shape_filter_length - 1) / 2
        )  # convert filter length into the span
        self.pulse_shape_filter = self._rrc_taps(
            pulse_shape_filter_span, signal_description.excess_bandwidth
        )
        filtered = torchsig_convolve(
            zero_padded, self.pulse_shape_filter, gpu=self.use_gpu
        )

        if not self.random_data:
            np.random.set_state(orig_state)  # return numpy back to its previous state

        return filtered[-self.num_iq_samples :]

    def _rrc_taps(self, size_in_symbols: int, alpha: float = 0.35) -> np.ndarray:
        # this could be made into a transform
        M = size_in_symbols
        Ns = float(self.iq_samples_per_symbol)
        n = np.arange(-M * Ns, M * Ns + 1)
        taps = np.zeros(int(2 * M * Ns + 1))
        for i in range(int(2 * M * Ns + 1)):
            # handle the discontinuity at t=+-Ns/(4*alpha)
            if n[i] * 4 * alpha == Ns or n[i] * 4 * alpha == -Ns:
                taps[i] = (
                    1
                    / 2.0
                    * (
                        (1 + alpha) * np.sin((1 + alpha) * np.pi / (4.0 * alpha))
                        - (1 - alpha) * np.cos((1 - alpha) * np.pi / (4.0 * alpha))
                        + (4 * alpha)
                        / np.pi
                        * np.sin((1 - alpha) * np.pi / (4.0 * alpha))
                    )
                )
            else:
                taps[i] = 4 * alpha / (np.pi * (1 - 16 * alpha**2 * (n[i] / Ns) ** 2))
                taps[i] = taps[i] * (
                    np.cos((1 + alpha) * np.pi * n[i] / Ns)
                    + np.sinc((1 - alpha) * n[i] / Ns)
                    * (1 - alpha)
                    * np.pi
                    / (4.0 * alpha)
                )
        return taps


class OFDMDataset(SyntheticDataset):
    """OFDM Dataset

    Args:
        constellations (:obj:`list` or :obj:`tuple`):
            Sequence of strings representing the set of possible sub-carrier modulations. All sub-carriers are modulated
            with the same modulation or they are randomly modulated per subcarrier with equal probability.

        num_subcarriers (:obj:`list` or :obj:`tuple`):
            Sequence of ints that represent the different number of subcarriers to include.

        cyclic_prefix_ratio (:obj:`list` or :obj:`tuple`):
            Sequence of possible cyclic_prefix_ratios to use. The cyclic prefix length will be an
            element cyclic_prefix_ratio times an element of num_subcarriers

        num_iq_samples (:obj:`int`):
            number of samples to produce for each waveform

        num_samples_per_class (:obj:`int`):
            number of samples to be kept for each class

        random_data (:obj:`bool`):
            whether the modulated binary utils should be random each time, or seeded by index

        sidelobe_suppression_methods (:obj:`tuple`):
            Tuple of possible sidelobe suppression methods. The options are:
                - `none` ~ Perform no sidelobe suppression methods
                - `lpf` ~ Apply a static low pass filter to the OFDM signal
                - `rand_lpf` ~ Apply a low pass filter with a randomized cutoff frequency to the OFDM signal
                - `win_start` ~ Apply a windowing method starting at the symbol boundary
                - `win_center` ~ Apply a windowing method centered at the symbol boundary
            For more details on the windowing method options, please see:
            http://zone.ni.com/reference/en-XX/help/373725J-01/wlangen/windowing/

        dc_subcarrier (:obj:`tuple`):
            Tuple of possible DC subcarrier options:
                - `(on,)` ~ Always leave the DC subcarrier on
                - `(off,)` ~ Always turn the DC subcarrier off
                - `(on, off)` ~ Half with DC subcarrier on and half off

        time_varying_realism (:obj:`tuple`):
            Tuple of on/off/both options for adding time-varying realistic effects in the form of
            bursts, pilot carriers, and resource blocks. Options:
                - `(on,)` ~ Leave the time-varying effects on, with half under full bursty effects and half under partial
                - `(off,)` ~ Always leave the time-varying effects off
                - `(on, off)` ~ One third with full bursty effects, one third with partial, and one third off
                - `(full_bursty,)` ~ All signals are bursty with consistent pattern throughout
                - `(partial_bursty,)` ~ All signals are mixed with bursty and continuous regions
            Note: The partial bursty behavior occurs prior to time slicing, and as such, is more interesting in longer
            duration examples

        transform (:obj:`Callable`, optional):
            A function/transform that takes in an IQ vector and returns a transformed version.

    """

    def __init__(
        self,
        constellations: Optional[Union[List, Tuple]] = ("bpsk", "qpsk"),
        num_subcarriers: IntParameter = (64, 128, 256, 512, 1024, 2048),
        cyclic_prefix_ratios: FloatParameter = (0.125, 0.25),
        num_iq_samples: int = 100,
        num_samples_per_class: int = 100,
        random_data: bool = False,
        sidelobe_suppression_methods: tuple = (
            "none",
            "lpf",
            "rand_lpf",
            "win_start",
            "win_center",
        ),
        dc_subcarrier: tuple = ("on", "off"),
        time_varying_realism: tuple = ("off",),
        use_gpu: bool = False,
        **kwargs,
    ):
        super(OFDMDataset, self).__init__(**kwargs)
        self.constellations = constellations
        self.num_iq_samples = num_iq_samples
        self.num_samples_per_class = num_samples_per_class
        self.random_data = random_data
        self.use_gpu = use_gpu
        self.index = []
        if "lpf" in sidelobe_suppression_methods:
            # Precompute LPF
            cutoff = 0.3
            transition_bandwidth = (0.5 - cutoff) / 4
            num_taps = estimate_filter_length(transition_bandwidth)
            self.taps = sp.firwin(
                num_taps,
                cutoff,
                width=transition_bandwidth,
                window=sp.get_window("blackman", num_taps),
                scale=True,
                fs=1,
            )

        # Precompute all possible random symbols for speed at sample generation
        self.random_symbols = []
        for const_name in self.constellations:
            const = default_const_map[const_name] / np.mean(
                np.abs(default_const_map[const_name])
            )
            self.random_symbols.append(const)

        subcarrier_modulation_types = ("fixed", "random")
        if "on" in time_varying_realism:
            if "off" in time_varying_realism:
                time_varying_realism = ("off", "full_bursty", "partial_bursty")
            else:
                time_varying_realism = ("full_bursty", "partial_bursty")
        combinations = list(
            itertools.product(
                constellations,
                subcarrier_modulation_types,
                cyclic_prefix_ratios,
                sidelobe_suppression_methods,
                dc_subcarrier,
                time_varying_realism,
            )
        )

        for class_idx, num_subcarrier in enumerate(num_subcarriers):
            class_name = "ofdm-{}".format(num_subcarrier)
            for idx in range(self.num_samples_per_class):
                (
                    const_name,
                    mod_type,
                    cyclic_prefix_ratio,
                    sidelobe_suppression_method,
                    dc_subcarrier,
                    time_varying_realism,
                ) = combinations[np.random.randint(len(combinations))]
                signal_description = SignalDescription(
                    sample_rate=0,
                    bits_per_symbol=2,
                    samples_per_symbol=2,  # Not accurate, but useful in calculating effective half bandwidth target
                    class_name=class_name,
                )
                self.index.append(
                    (
                        class_name,
                        class_idx * self.num_samples_per_class + idx,
                        num_subcarrier,
                        cyclic_prefix_ratio * num_subcarrier,
                        const_name,
                        mod_type,
                        sidelobe_suppression_method,
                        dc_subcarrier,
                        time_varying_realism,
                        signal_description,
                    )
                )

    def _generate_samples(self, item: Tuple) -> np.ndarray:
        index = item[1]
        num_subcarriers = item[2]
        cyclic_prefix_len = item[3]
        const_name = item[4]
        mod_type = item[5]
        sidelobe_suppression_method = item[6]
        dc_subcarrier = item[7]
        time_varying_realism = item[8]
        orig_state = np.random.get_state()
        if not self.random_data:
            np.random.seed(index)
            
        if mod_type == "random":
            symbols_idxs = np.random.randint(0, 1024, size=self.num_iq_samples)
            const_idxes = np.random.choice(
                range(len(self.random_symbols)), size=num_subcarriers
            )
            symbols = np.zeros(self.num_iq_samples, dtype=np.complex128)
            for subcarrier_idx, const_idx in enumerate(const_idxes):
                begin_idx = (self.num_iq_samples) * subcarrier_idx
                end_idx = (self.num_iq_samples) * (subcarrier_idx + 1)
                symbols[begin_idx:end_idx] = self.random_symbols[const_idx][
                    np.mod(
                        symbols_idxs[begin_idx:end_idx],
                        len(self.random_symbols[const_idx]),
                    )
                ]
        else:
            # Fixed modulation across all subcarriers
            const_name = np.random.choice(self.constellations)
            const = default_const_map[const_name] / np.mean(
                np.abs(default_const_map[const_name])
            )
            symbol_nums = np.random.randint(0, len(const), int(self.num_iq_samples))
            symbols = const[symbol_nums]
        divisible_index = -(len(symbols) % num_subcarriers)
        if divisible_index != 0:
            symbols = symbols[:divisible_index]

        # now sub-carrier modulate
        serial_to_parallel = symbols.reshape(num_subcarriers, -1)
        zero_pad = np.pad(
            serial_to_parallel,
            ((int(num_subcarriers / 2), int(num_subcarriers / 2)), (0, 0)),
            "constant",
            constant_values=0,
        )

        # Turn off DC subcarrier
        if dc_subcarrier == "off":
            dc_center = int(zero_pad.shape[0] // 2)
            zero_pad[dc_center, :] = np.zeros((zero_pad.shape[1]))

        # Add time-varying realism with randomized bursts, pilots, and resource blocks
        burst_dur = 1
        original_on = False
        if (
            time_varying_realism == "full_bursty"
            or time_varying_realism == "partial_bursty"
        ):
            # Bursty
            if time_varying_realism == "full_bursty":
                burst_region_start = 0
                burst_region_stop = zero_pad.shape[1]
            else:
                burst_region_start = np.random.uniform(0.0, 0.9)
                burst_region_dur = min(
                    1.0 - burst_region_start, np.random.uniform(0.25, 1.0)
                )
                burst_region_start = int(burst_region_start * zero_pad.shape[1] // 4)
                burst_region_dur = int(burst_region_dur * zero_pad.shape[1] // 4)
                burst_region_stop = burst_region_start + burst_region_dur
            # bursty = deepcopy(zero_pad)
            bursty = pickle.loads(
                pickle.dumps(zero_pad, -1)
            )  # no random hangs like deepcopy

            burst_dur = np.random.choice([1, 2, 4])
            original_on = True if np.random.rand() <= 0.5 else False
            for subcarrier_idx in range(bursty.shape[0]):
                on = original_on
                for time_idx in range(bursty.shape[1]):
                    if time_idx % burst_dur == 0:
                        on = not on
                    if (not on) and (
                        time_idx >= burst_region_start and time_idx <= burst_region_stop
                    ):
                        bursty[subcarrier_idx, time_idx] = 0 + 1j * 0

            # Pilots
            min_num_pilots = 4
            max_num_pilots = int(num_subcarriers // 8)
            num_pilots = np.random.randint(min_num_pilots, max_num_pilots)
            pilot_indices = np.random.choice(
                range(num_subcarriers), num_pilots, replace=False
            )
            bursty[pilot_indices + num_subcarriers // 2, :] = zero_pad[
                pilot_indices + num_subcarriers // 2, :
            ]

            # Resource blocks
            min_num_blocks = 2
            max_num_blocks = 16
            num_blocks = np.random.randint(min_num_blocks, max_num_blocks)
            for block_idx in range(num_blocks):
                block_start = np.random.uniform(0.0, 0.9)
                block_dur = np.random.uniform(0.05, 1.0 - block_start)
                block_start = int(block_start * zero_pad.shape[1])
                block_dur = int(block_dur * zero_pad.shape[1] // 4)
                block_stop = block_start + block_dur

                block_low_carrier = np.random.randint(0, num_subcarriers - 4)
                block_num_carriers = np.random.randint(1, num_subcarriers // 8)
                block_high_carrier = min(
                    block_low_carrier + block_num_carriers, num_subcarriers
                )

                bursty[
                    block_low_carrier
                    + num_subcarriers // 2 : block_high_carrier
                    + num_subcarriers // 2,
                    block_start:block_stop,
                ] = zero_pad[
                    block_low_carrier
                    + num_subcarriers // 2 : block_high_carrier
                    + num_subcarriers // 2,
                    block_start:block_stop,
                ]
            zero_pad = bursty

        ofdm_symbols = np.fft.ifft(np.fft.ifftshift(zero_pad, axes=0), axis=0)
        symbol_dur = ofdm_symbols.shape[0]
        cyclic_prefixed = np.pad(
            ofdm_symbols, ((int(cyclic_prefix_len), 0), (0, 0)), "wrap"
        )

        if sidelobe_suppression_method == "none":
            output = cyclic_prefixed.T.flatten()

        elif sidelobe_suppression_method == "lpf":
            flattened = cyclic_prefixed.T.flatten()
            # Apply pre-computed LPF
            output = torchsig_convolve(flattened, self.taps, gpu=self.use_gpu)[:-50]

        elif sidelobe_suppression_method == "rand_lpf":
            flattened = cyclic_prefixed.T.flatten()
            # Generate randomized LPF
            cutoff = np.random.uniform(0.25, 0.475)
            transition_bandwidth = (0.5 - cutoff) / 4
            num_taps = estimate_filter_length(transition_bandwidth)
            taps = sp.firwin(
                num_taps,
                cutoff,
                width=transition_bandwidth,
                window=sp.get_window("blackman", num_taps),
                scale=True,
                fs=1,
            )
            # Apply random LPF
            output = torchsig_convolve(flattened, taps, gpu=self.use_gpu)[:-num_taps]
        else:
            # Apply appropriate windowing technique
            window_len = cyclic_prefix_len
            half_window_len = int(window_len / 2)
            if sidelobe_suppression_method == "win_center":
                windowed = np.pad(
                    cyclic_prefixed,
                    ((half_window_len, half_window_len), (0, 0)),
                    "constant",
                    constant_values=0,
                )
                windowed[-half_window_len:, :] = windowed[
                    int(half_window_len)
                    + int(cyclic_prefix_len) : int(half_window_len)
                    + int(cyclic_prefix_len)
                    + int(half_window_len),
                    :,
                ]
                windowed[:half_window_len, :] = windowed[
                    int(half_window_len)
                    + int(cyclic_prefix_len)
                    + int(symbol_dur) : int(half_window_len)
                    + int(cyclic_prefix_len)
                    + int(symbol_dur)
                    + int(half_window_len),
                    :,
                ]
            elif sidelobe_suppression_method == "win_start":
                windowed = np.pad(
                    cyclic_prefixed,
                    ((0, int(window_len)), (0, 0)),
                    "constant",
                    constant_values=0,
                )
                windowed[-int(window_len) :, :] = windowed[
                    int(cyclic_prefix_len) : int(cyclic_prefix_len) + int(window_len), :
                ]
            else:
                raise ValueError(
                    "Expected window method to be: none, win_center, or win_start. Received: {}".format(
                        self.window_method
                    )
                )

            # window the tails
            front_window = np.blackman(int(window_len * 2))[: int(window_len)].reshape(
                -1, 1
            )
            tail_window = np.blackman(int(window_len * 2))[-int(window_len) :].reshape(
                -1, 1
            )
            windowed[: int(window_len), :] = (
                front_window * windowed[: int(window_len), :]
            )
            windowed[-int(window_len) :, :] = (
                tail_window * windowed[-int(window_len) :, :]
            )

            combined = np.zeros((windowed.shape[0] * windowed.shape[1],), dtype=complex)
            start_idx = 0
            for symbol_idx in range(windowed.shape[1]):
                combined[start_idx : start_idx + windowed.shape[0]] += windowed[
                    :, symbol_idx
                ]
                start_idx += symbol_dur + int(window_len)
            output = combined[
                : int(cyclic_prefixed.shape[0] * cyclic_prefixed.shape[1])
            ]

        # Randomize the start index (while bypassing the initial windowing if present)
        if num_subcarriers * 4 * burst_dur < self.num_iq_samples:
            start_idx = np.random.randint(0, output.shape[0] - self.num_iq_samples)
        else:
            if original_on:
                lower = max(0, int(symbol_dur * burst_dur) - self.num_iq_samples * 0.7)
                upper = min(
                    int(symbol_dur * burst_dur), output.shape[0] - self.num_iq_samples
                )
                start_idx = np.random.randint(lower, upper)
            elif "win" in sidelobe_suppression_method:
                start_idx = np.random.randint(
                    window_len, int(symbol_dur * burst_dur) + window_len
                )
            else:
                start_idx = np.random.randint(0, int(symbol_dur * burst_dur))

        if not self.random_data:
            np.random.set_state(orig_state)  # return numpy back to its previous state

        return output[start_idx : start_idx + self.num_iq_samples]


class FSKDataset(SyntheticDataset):
    """FSK Dataset

    Args:
        modulations (:obj:`list` or :obj:`tuple`):
            Sequence of strings representing the modulations that should be included

        num_iq_samples (:obj:`int`):
            number of samples to read from each file in the database

        num_samples_per_class (:obj:`int`):
            number of samples to be kept for each class

        iq_samples_per_symbol (:obj:`int`):
            number of IQ samples per symbol

        random_data (:obj:`bool`):
            whether the modulated binary utils should be random each time, or seeded by index

        transform (:obj:`Callable`, optional):
            A function/transform that takes in an IQ vector and returns a transformed version.

    """

    def __init__(
        self,
        modulations: Optional[Union[List, Tuple]] = ("2fsk", "2gmsk"),
        num_iq_samples: int = 100,
        num_samples_per_class: int = 100,
        iq_samples_per_symbol: int = 2,
        random_data: bool = False,
        random_pulse_shaping: bool = False,
        use_gpu: bool = False,
        **kwargs,
    ):
        super(FSKDataset, self).__init__(**kwargs)
        self.modulations = list(freq_map.keys()) if modulations is None else modulations
        self.num_iq_samples = num_iq_samples
        self.num_samples_per_class = num_samples_per_class
        self.iq_samples_per_symbol = iq_samples_per_symbol
        self.random_data = random_data
        self.random_pulse_shaping = random_pulse_shaping
        self.use_gpu = use_gpu
        self.index = []

        for freq_idx, freq_name in enumerate(map(str.lower, self.modulations)):
            for idx in range(self.num_samples_per_class):
                # modulation index scales the bandwidth of the signal, and
                # iq_samples_per_symbol is used as an oversampling rate in
                # FSKDataset class, therefore the signal bandwidth can be
                # approximated by mod_idx/iq_samples_per_symbol.
                mod_idx = self._mod_index(freq_name)
                bandwidth_cutoff = mod_idx / self.iq_samples_per_symbol
                bandwidth = (
                    np.random.uniform(
                        bandwidth_cutoff,
                        0.5 - bandwidth_cutoff,  # normalized sampling rate fs=1
                    )
                    if self.random_pulse_shaping
                    else 0.0
                )
                signal_description = SignalDescription(
                    sample_rate=0,
                    bits_per_symbol=np.log2(len(freq_map[freq_name])),
                    samples_per_symbol=iq_samples_per_symbol,
                    class_name=freq_name,
                    excess_bandwidth=bandwidth,
                )
                self.index.append(
                    (
                        freq_name,
                        freq_idx * self.num_samples_per_class + idx,
                        bandwidth,
                        signal_description,
                    )
                )

    def _generate_samples(self, item: Tuple) -> np.ndarray:
        const_name = item[0]
        index = item[1]
        bandwidth = item[2]
        signal_description = item[3]

        # calculate the modulation order, ex: the "4" in "4-FSK"
        const = freq_map[const_name]
        mod_order = len(const)

        # samples per symbol presumably used as a bandwidth measure (ex: BW=1/SPS),
        # but does not work for FSK. samples per symbol is redefined into
        # the "oversampling rate", and samples per symbol is instead derived
        # from the modulation order
        oversampling_rate = np.copy(self.iq_samples_per_symbol)
        samples_per_symbol_recalculated = mod_order * oversampling_rate

        # scale the frequency map by the oversampling rate such that the tones
        # are packed tighter around f=0 the larger the oversampling rate
        const_oversampled = const / oversampling_rate

        orig_state = np.random.get_state()
        if not self.random_data:
            np.random.seed(index)

        symbol_nums = np.random.randint(
            0,
            len(const_oversampled),
            int(self.num_iq_samples / samples_per_symbol_recalculated),
        )

        symbols = const_oversampled[symbol_nums]
        symbols_repeat = np.repeat(symbols, samples_per_symbol_recalculated)

        if "g" in const_name:
            # GMSK, GFSK
            taps = self._gaussian_taps(samples_per_symbol_recalculated, bandwidth)
            signal_description.excess_bandwidth = bandwidth
            filtered = torchsig_convolve(symbols_repeat, taps, gpu=self.use_gpu)
        else:
            # FSK, MSK
            filtered = symbols_repeat

        # insert a zero at first sample to start at zero phase
        filtered = np.insert(filtered, 0, 0)

        mod_idx = self._mod_index(const_name)
        phase = np.cumsum(np.array(filtered) * 1j * mod_idx * np.pi)
        modulated = np.exp(phase)

        if self.random_pulse_shaping:
            # Apply a randomized LPF simulating a noisy detector/burst extractor, then downsample to ~fs/2 bw
            # accept the cutoff-frequency of the filter as external
            # parameter, randomized as part of outer framework
            cutoff_frequency = bandwidth
            # calculate transition bandwidth. a larger cutoff frequency requires
            # a smaller transition bandwidth, and a smaller cutoff frequency
            # allows for a larger transition bandwidth
            transition_bandwidth = (1.0 / 2 - (cutoff_frequency)) / 4
            # estimate number of taps needed to implement filter
            num_taps = estimate_filter_length(transition_bandwidth)

            # design the filter
            taps = sp.firwin(
                num_taps,
                cutoff_frequency,
                width=transition_bandwidth,
                window=sp.get_window("blackman", num_taps),
                scale=True,
                fs=1,
            )
            # apply the filter
            modulated = torchsig_convolve(modulated, taps, gpu=self.use_gpu)

        if not self.random_data:
            np.random.set_state(orig_state)  # return numpy back to its previous state

        return modulated[-self.num_iq_samples :]

    def _gaussian_taps(self, samples_per_symbol, BT: float = 0.35) -> np.ndarray:
        # pre-modulation Bb*T product which sets the bandwidth of the Gaussian lowpass filter
        M = 4  # duration in symbols
        n = np.arange(-M * samples_per_symbol, M * samples_per_symbol + 1)
        p = np.exp(
            -2 * np.pi**2 * BT**2 / np.log(2) * (n / float(samples_per_symbol)) ** 2
        )
        p = p / np.sum(p)
        return p

    def _mod_index(self, const_name):
        # returns the modulation index based on the modulation
        if "gfsk" in const_name:
            # bluetooth
            mod_idx = 0.32
        elif "msk" in const_name:
            # MSK, GMSK
            mod_idx = 0.5
        else:
            # FSK
            mod_idx = 1.0
        return mod_idx


class AMDataset(SyntheticDataset):
    """AM Dataset

    Args:
        transform (:obj:`Callable`, optional):
            A function/transform that takes in an IQ vector and returns a transformed version.

    """

    def __init__(
        self,
        num_iq_samples: int = 100,
        num_samples_per_class: int = 100,
        random_data: bool = False,
        **kwargs,
    ):
        super(AMDataset, self).__init__(**kwargs)
        self.num_iq_samples = num_iq_samples
        self.num_samples_per_class = num_samples_per_class
        self.classes = ["am", "am-ssb", "am-dsb"]
        self.random_data = random_data
        self.index = []

        for class_idx, class_name in enumerate(self.classes):
            signal_description = SignalDescription(sample_rate=0)
            for idx in range(self.num_samples_per_class):
                self.index.append(
                    (
                        class_name,
                        class_idx * self.num_samples_per_class + idx,
                        signal_description,
                    )
                )

    def __len__(self) -> int:
        return len(self.index)

    def _generate_samples(self, item: Tuple) -> np.ndarray:
        const_name = item[0]
        index = item[1]
        orig_state = np.random.get_state()
        if not self.random_data:
            np.random.seed(index)

        source = np.random.randn(self.num_iq_samples) + 0j
        taps = sp.firwin(
            100,  # num taps
            0.5 if "ssb" not in const_name else 0.25,
            0.5 / 16 if "ssb" not in const_name else 0.25 / 4,
            window="blackman",
        )
        filtered = np.convolve(source, taps, "same")
        sinusoid = np.exp(2j * np.pi * 0.125 * np.arange(self.num_iq_samples))
        filtered *= np.ones_like(filtered) if "ssb" not in const_name else sinusoid
        filtered += 5 if const_name == "am" else 0

        if not self.random_data:
            np.random.set_state(orig_state)  # return numpy back to its previous state

        return filtered[-self.num_iq_samples :]


class FMDataset(SyntheticDataset):
    """FM Dataset

    Args:
        transform (:obj:`Callable`, optional):
            A function/transform that takes in an IQ vector and returns a transformed version.

    """

    def __init__(
        self,
        num_iq_samples: int = 100,
        num_samples_per_class: int = 100,
        random_data: bool = False,
        **kwargs,
    ):
        super(FMDataset, self).__init__(**kwargs)
        self.num_iq_samples = num_iq_samples
        self.num_samples_per_class = num_samples_per_class
        self.classes = ["fm"]
        self.random_data = random_data
        self.index = []

        for class_idx, class_name in enumerate(self.classes):
            signal_description = SignalDescription(sample_rate=0)
            for idx in range(self.num_samples_per_class):
                self.index.append(
                    (
                        class_name,
                        class_idx * self.num_samples_per_class + idx,
                        signal_description,
                    )
                )

    def __len__(self) -> int:
        return len(self.index)

    def _generate_samples(self, item: Tuple) -> np.ndarray:
        # class_name = item[0]
        index = item[1]
        orig_state = np.random.get_state()
        if not self.random_data:
            np.random.seed(index)

        source = np.random.randn(self.num_iq_samples) + 0j
        modulated = np.exp(1j * np.pi / 2 * np.cumsum(source) / 2.0)

        if not self.random_data:
            np.random.set_state(orig_state)  # return numpy back to its previous state

        return modulated[-self.num_iq_samples :]
