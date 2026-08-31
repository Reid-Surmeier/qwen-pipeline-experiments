#!/usr/bin/env bash
# Assemble the deliverable set from the best stage of each map, then apply the
# deterministic repairs. Order matters: furniture is cleared first so the border
# restore cannot trace round a box that is about to be deleted, and insets are
# pasted last so nothing later paints over them.
set -u
cd "$(dirname "$0")/.."
OUT=benchmarks/regional/final
rm -rf "$OUT"; mkdir -p "$OUT"

# sheets whose sources draw country borders in white, so the recolour leaves none
NEEDS_BORDERS="asia middle-east"

for r in africa south-america asia usa canada russia australia caribbean europe middle-east; do
  img=""
  for st in B3-subjects C-final B2-recoloured; do
    p="benchmarks/regional/runs/$r/$st/image-01.png"
    [ -f "$p" ] && { img="$p"; stage="$st"; break; }
  done
  [ -n "$img" ] || { echo "!! $r: nothing to finalise"; continue; }

  python3 scripts/map_clear_furniture.py --image "$img" --out "/tmp/f1-$r.png" >/dev/null
  step="furniture"

  case " $NEEDS_BORDERS " in
    *" $r "*)
      python3 scripts/map_restore_borders.py \
        --geometry "benchmarks/regional/runs/$r/A-stripped/image-01.png" \
        --image "/tmp/f1-$r.png" --out "/tmp/f2-$r.png" >/dev/null
      step="$step + borders" ;;
    *) cp "/tmp/f1-$r.png" "/tmp/f2-$r.png" ;;
  esac

  python3 scripts/map_restore_insets.py --region "$r" \
      --source "benchmarks/regional/reference/$r.png" \
      --image "/tmp/f2-$r.png" --out "$OUT/$r.png" >/dev/null
  [ "$r" = usa ] && step="$step + insets"

  printf "%-15s %-24s <- %s\n" "$r" "$step" "$stage"
done
