import neo4j
from typing import List, Dict, Set, Any
from .models import NodeModel, EdgeModel

def _add_node_from_neo4j_node(node_obj: neo4j.graph.Node, nodes_map: Dict[str, NodeModel]):
    if node_obj and node_obj.element_id and not nodes_map.get(node_obj.element_id):
        node_id = node_obj.element_id
        labels = list(node_obj.labels)
        properties = dict(node_obj) # Corrected: Node object itself is a mapping
        
        default_label_text = labels[0] if labels else (properties.get("name") or f"Node ({node_id[:6]}...)")
        group_text = labels[0] if labels else properties.get("group", "Unknown")

        tooltip_parts = [f"ID: {node_id}"]
        if labels:
            tooltip_parts.append(f"Labels: {', '.join(labels)}")
        if properties:
            tooltip_parts.append("Properties:")
            for key, value in properties.items():
                tooltip_parts.append(f"  {key}: {value}")

        nodes_map[node_id] = NodeModel(
            id=node_id,
            label=str(default_label_text), # Ensure label is a string
            group=str(group_text), # Ensure group is a string
            properties=properties,
            title="\n".join(tooltip_parts)
        )

def _process_neo4j_relationship(rel_obj: neo4j.graph.Relationship, nodes_map: Dict[str, NodeModel], edges_list: List[EdgeModel], processed_rel_ids: Set[str]):
    if rel_obj and rel_obj.element_id and rel_obj.element_id not in processed_rel_ids:
        rel_id = rel_obj.element_id
        start_node_id = rel_obj.start_node.element_id
        end_node_id = rel_obj.end_node.element_id
        rel_type = rel_obj.type
        properties = dict(rel_obj) # Corrected: Relationship object itself is a mapping

        if start_node_id not in nodes_map:
            _add_node_from_neo4j_node(rel_obj.start_node, nodes_map)
        if end_node_id not in nodes_map:
            _add_node_from_neo4j_node(rel_obj.end_node, nodes_map)
            
        source_node_display_label = nodes_map.get(start_node_id).label if start_node_id in nodes_map else f"Node {start_node_id[:6]}..."
        target_node_display_label = nodes_map.get(end_node_id).label if end_node_id in nodes_map else f"Node {end_node_id[:6]}..."

        tooltip_parts = [
            f"ID: {rel_id}",
            f"Type: {rel_type}",
            f"Source: {source_node_display_label} ({start_node_id[:6]}...)",
            f"Target: {target_node_display_label} ({end_node_id[:6]}...)"
        ]
        if properties:
            tooltip_parts.append("Properties:")
            for key, value in properties.items():
                tooltip_parts.append(f"  {key}: {value}")
        
        edges_list.append(EdgeModel(
            id=rel_id,
            from_node=start_node_id, # Pydantic will use alias 'from'
            to_node=end_node_id,     # Pydantic will use alias 'to'
            label=rel_type,
            properties=properties,
            title="\n".join(tooltip_parts)
        ))
        processed_rel_ids.add(rel_id)

def _add_node_from_info_dict(node_info_dict: Dict[str, Any], nodes_map: Dict[str, NodeModel]):
    node_id = node_info_dict.get("id")
    if node_id and not nodes_map.get(node_id):
        labels = node_info_dict.get("labels", [])
        properties = node_info_dict.get("properties", {})
        
        default_label_text = labels[0] if labels else (properties.get("name") or f"Node ({str(node_id)[:6]}...)")
        group_text = labels[0] if labels else properties.get("group", "Unknown")

        tooltip_parts = [f"ID: {node_id}"]
        if labels:
            tooltip_parts.append(f"Labels: {', '.join(labels)}")
        if properties:
            tooltip_parts.append("Properties:")
            for key, value in properties.items():
                tooltip_parts.append(f"  {key}: {value}")

        nodes_map[node_id] = NodeModel(
            id=str(node_id),
            label=str(default_label_text),
            group=str(group_text),
            properties=properties,
            title="\n".join(tooltip_parts)
        )

def _process_relationship_from_info_dict(rel_info_dict: Dict[str, Any], nodes_map: Dict[str, NodeModel], edges_list: List[EdgeModel], processed_rel_ids: Set[str]):
    rel_id = rel_info_dict.get("id")
    if rel_id and rel_id not in processed_rel_ids:
        start_node_id = str(rel_info_dict["start"])
        end_node_id = str(rel_info_dict["end"])
        rel_type = rel_info_dict["type"]
        properties = rel_info_dict.get("properties", {})

        if start_node_id not in nodes_map:
            _add_node_from_info_dict({"id": start_node_id, "properties": {"name": f"Node {start_node_id[:6]}..."}}, nodes_map)
        if end_node_id not in nodes_map:
            _add_node_from_info_dict({"id": end_node_id, "properties": {"name": f"Node {end_node_id[:6]}..."}}, nodes_map)

        source_node_display_label = nodes_map.get(start_node_id).label if start_node_id in nodes_map else f"Node {start_node_id[:6]}..."
        target_node_display_label = nodes_map.get(end_node_id).label if end_node_id in nodes_map else f"Node {end_node_id[:6]}..."
        
        tooltip_parts = [
            f"ID: {rel_id}",
            f"Type: {rel_type}",
            f"Source: {source_node_display_label} ({start_node_id[:6]}...)",
            f"Target: {target_node_display_label} ({end_node_id[:6]}...)"
        ]
        if properties:
            tooltip_parts.append("Properties:")
            for key, value in properties.items():
                tooltip_parts.append(f"  {key}: {value}")

        edges_list.append(EdgeModel(
            id=str(rel_id),
            from_node=start_node_id,
            to_node=end_node_id,
            label=str(rel_type),
            properties=properties,
            title="\n".join(tooltip_parts)
        ))
        processed_rel_ids.add(rel_id)