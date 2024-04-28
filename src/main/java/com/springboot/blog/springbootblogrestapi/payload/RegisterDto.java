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
        description = "RegisterDto Model Information"
)
public class RegisterDto {
    @Schema(
            description = "Enter your name"
    )
    private String name;

    @Schema(
            description = "Enter the username"
    )
    private String username;

    @Schema(
            description = "Enter your email address"
    )
    private String email;

    @Schema(
            description = "Provide password"
    )
    private String password;
}
