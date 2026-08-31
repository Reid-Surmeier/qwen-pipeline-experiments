#!/usr/bin/env bash
# Rebuild one regional sheet end to end: strip furniture, generate donors,
# assemble region by region, then chain furniture passes until no clock readout
# survives. Every stage is gated -- picking a pass by ink alone once chose a map
# with 96% of its fills wiped, because a blank map is mostly text.
set -u
cd "$(dirname "$0")/.."
r="$1"
src="benchmarks/regional/reference/$r.png"
B=scripts/bench_image_model.py
size=$(python3 -c "
import importlib.util;from pathlib import Path
s=importlib.util.spec_from_file_location('rb','scripts/regional_batch.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
print(m.size_for(Path('$src')))")
score() { python3 -c "
import sys;sys.path.insert(0,'scripts')
from score_pass import stats;from pathlib import Path
print(stats(Path('$1'))['$2'])"; }

echo "===== $r  $size"
ref_fill=$(score "$src" fill)

best=0; bestdir=""
for a in $(seq 1 8); do
  if python3 $B --timeout 600 --model meta/muse-image --label "$r-A$a" \
      --prompt-file benchmarks/regional/prompts/passA-strip-times.txt \
      --reference "$src" --size $size --out /tmp/rb-$r-A$a >/dev/null 2>&1; then
    f=$(score /tmp/rb-$r-A$a/image-01.png fill); i=$(score /tmp/rb-$r-A$a/image-01.png ink)
    echo "  A$a fill $f ink $i"
    python3 -c "import sys;sys.exit(0 if float('$f')>=float('$ref_fill')*0.80 and float('$i')>float('$best') else 1)" \
      && { best=$i; bestdir=/tmp/rb-$r-A$a; }
  else echo "  A$a filtered"; fi
  sleep 3
done
[ -n "$bestdir" ] || { echo "!! no usable pass A"; exit 1; }
mkdir -p benchmarks/regional/runs/$r/A-stripped
cp $bestdir/image-01.png benchmarks/regional/runs/$r/A-stripped/image-01.png
echo "  chose $bestdir"

a_img=benchmarks/regional/runs/$r/A-stripped/image-01.png
dsize=$(python3 -c "from PIL import Image; w,h=Image.open('$a_img').size; print(f'{w}x{h}')")
for d in 1 2 3 4 5 6; do
  for a in 1 2 3; do
    if python3 $B --timeout 600 --model meta/muse-image --label "$r-d$d" \
        --prompt-file benchmarks/regional/prompts/passB-$r.txt \
        --reference "$a_img" --size $dsize \
        --out benchmarks/regional/runs/$r/donor-$d >/dev/null 2>&1; then
      f=$(score benchmarks/regional/runs/$r/donor-$d/image-01.png fill)
      echo "  donor $d fill $f"
      python3 -c "import sys;sys.exit(0 if float('$f')>=float('$ref_fill')*0.80 else 1)" && break
      rm -rf benchmarks/regional/runs/$r/donor-$d
    fi
    sleep 3
  done
done

python3 scripts/map_assembly.py --reference "$a_img" \
  $(for d in 1 2 3 4 5 6; do f=benchmarks/regional/runs/$r/donor-$d/image-01.png; [ -f "$f" ] && echo "--donor $f"; done) \
  --out benchmarks/regional/runs/$r/assembled/image-01.png --grid 6

mkdir -p benchmarks/regional/runs/$r/C-final
cp benchmarks/regional/runs/$r/assembled/image-01.png benchmarks/regional/runs/$r/C-final/image-01.png
for round in 1 2 3 4; do
  cur=benchmarks/regional/runs/$r/C-final/image-01.png
  before=$(score "$cur" boxes)
  echo "  furniture round $round: $before readouts"
  [ "$before" = "0" ] && break
  csize=$(python3 -c "from PIL import Image; w,h=Image.open('$cur').size; print(f'{w}x{h}')")
  moved=0
  for a in 1 2 3 4 5; do
    if python3 $B --timeout 600 --model meta/muse-image --label "$r-C$round$a" \
        --prompt-file benchmarks/regional/prompts/passC-clear-furniture.txt \
        --reference "$cur" --size $csize --out /tmp/rb-$r-C$round$a >/dev/null 2>&1; then
      after=$(score /tmp/rb-$r-C$round$a/image-01.png boxes)
      if python3 scripts/score_pass.py --before "$cur" --after /tmp/rb-$r-C$round$a/image-01.png >/dev/null 2>&1 \
         && python3 -c "import sys;sys.exit(0 if $after < $before else 1)"; then
        cp /tmp/rb-$r-C$round$a/image-01.png "$cur"; moved=1
        echo "    accepted ($before -> $after)"; break
      fi
    fi
    sleep 3
  done
  [ "$moved" = 0 ] && { echo "    no improvement"; break; }
done
echo "===== $r done"
