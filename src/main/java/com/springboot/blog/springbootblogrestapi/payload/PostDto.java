package com.springboot.blog.springbootblogrestapi.payload;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.Set;

@Data
public class PostDto {
    private long id;

    // title should not be null or empty
    // title should have atleast 2 characters
    @NotEmpty
    @Size(min = 2, message = "Post title should have atleast 2 characters")
    private String title;

    // post descripiton should be not null or empty
    // post description should have at least 10 characters
    @NotEmpty
    @Size(min = 10, message = "Post description should have at least 10 characters")
    private String description;

    // post content should not be null or empty
    @NotEmpty
    private String content;
    private Set<CommentDto> comments;
}