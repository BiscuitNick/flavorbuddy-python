import { useState } from "react";
import { Leaf } from "lucide-react";
import type { Content } from "../api";
export function FoodImage({
  recipe,
  large = false,
}: {
  recipe: Content;
  large?: boolean;
}) {
  const [broken, setBroken] = useState(false);
  const image = recipe.private_cover || recipe.image;
  return image && !broken ? (
    <img
      className={`food-image ${large ? "large" : ""}`}
      src={image}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setBroken(true)}
    />
  ) : (
    <div
      className={`food-image food-fallback ${large ? "large" : ""}`}
      aria-hidden="true"
    >
      <span className="plate">
        <Leaf size={large ? 82 : 52} strokeWidth={1} />
      </span>
      <span className="fallback-caption">Something good is cooking</span>
    </div>
  );
}

export function RecipeBody({ recipe }: { recipe: Content }) {
  return (
    <div className="recipe-body">
      <aside>
        <FoodImage recipe={recipe} large />
        <section className="ingredient-panel">
          <span className="eyebrow">WHAT YOU’LL NEED</span>
          <h2>Ingredients</h2>
          <ul>
            {recipe.ingredients.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </section>
      </aside>
      <section className="directions">
        <h2>Let’s make it.</h2>
        <ol>
          {recipe.instructions.map((step, i) => (
            <li key={i}>
              <span className="step-number">
                {String(i + 1).padStart(2, "0")}
              </span>
              <p>{step}</p>
            </li>
          ))}
        </ol>
        {recipe.notes && (
          <div className="personal-note">
            <span className="eyebrow">A NOTE FROM YOUR KITCHEN</span>
            <p className="preserve-lines">{recipe.notes}</p>
          </div>
        )}
      </section>
    </div>
  );
}
