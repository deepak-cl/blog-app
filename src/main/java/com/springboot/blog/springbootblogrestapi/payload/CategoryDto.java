package com.springboot.blog.springbootblogrestapi.payload;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Schema(
        description = "CategoryDto Model Information"
)
public class CategoryDto {
    private long id;

    @Schema(
            description = "Category Name"
    )
    private String name;

    @Schema(
            description = "Category Description"
    )
    private String description;
}
