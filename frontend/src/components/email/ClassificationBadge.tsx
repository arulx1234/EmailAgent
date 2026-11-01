import Badge from "../ui/Badge";

interface ClassificationBadgeProps {
  category: string;
}

export default function ClassificationBadge({
  category,
}: ClassificationBadgeProps) {
  const getVariant = () => {
    switch (category.toLowerCase()) {
      case "work":
      case "customer support":
        return "blue";

      case "security":
        return "red";

      case "github":
        return "red";

      case "finance":
        return "green";

      case "promotions":
      case "marketing":
        return "yellow";

      default:
        return "gray";
    }
  };

  return (
    <Badge variant={getVariant()}>
      {category.replace(/\b\w/g, (letter) => letter.toUpperCase())}
    </Badge>
  );
}
