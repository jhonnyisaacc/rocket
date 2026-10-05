"""Optional scientific figure from the synthetic surface (requires Matplotlib)."""

import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'research/governance/power'


def main():
    data=json.loads((FOLDER/'surface.json').read_text())
    plt.rcParams.update({'font.size':10,'svg.hashsalt':'rocket-power-20261005'})
    figure,axes=plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
    selected=[r for r in data['results'] if r['missingness']==0 and r['economic_drift_S']==0]
    for ax,gate,title in zip(axes,['primary_information','economic_evidence','full_pass'],['Predictive information gate','Economic evidence gate','Complete gate package'],strict=True):
        for scenario in ['independent','clustered','heavy_tailed','up_stronger','down_stronger']:
            rows=[r for r in selected if r['scenario']==scenario]
            x=[r['synthetic_r'] for r in rows]
            p=[r['probabilities'][gate]['probability'] for r in rows]
            low=[r['probabilities'][gate]['mc_95_interval'][0] for r in rows]
            high=[r['probabilities'][gate]['mc_95_interval'][1] for r in rows]
            line=ax.plot(x,p,label=scenario.replace('_',' '),marker='o',linewidth=1.5,markersize=3)[0]
            ax.fill_between(x,low,high,color=line.get_color(),alpha=.1)
        ax.set_title(title);ax.set_xlabel('Nominal synthetic oracle r');ax.set_xlim(0,.4)
        ax.grid(alpha=.2);ax.set_ylim(0,.02 if gate=='full_pass' else 1)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    axes[0].set_ylabel('Estimated synthetic gate PASS probability')
    axes[0].legend(fontsize=8,loc='upper left')
    axes[2].text(.02,.014,'0 / 2,000 complete passes\nin every regime shown\n95% MC upper bound ≈ 0.192%',fontsize=9)
    figure.suptitle('MOM-002 pre-outcome feasibility — conditional synthetic results',fontsize=14)
    figure.supxlabel('Complete-feature assumption; zero economic drift; 40bp; 2,000 draws/regime. Shading: Wilson Monte Carlo intervals.',fontsize=9)
    figure.savefig(FOLDER/'power_surface.svg',metadata={'Date':None})
    figure.savefig(FOLDER/'power_surface.png',dpi=180,metadata={'Software':'Rocket synthetic power audit'})
    plt.close(figure)


if __name__=='__main__':
    main()
